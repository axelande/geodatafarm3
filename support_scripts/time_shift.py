from bisect import bisect_left, bisect_right
from datetime import datetime
from typing import Self

STRATEGIES = ('nearest', 'previous', 'next', 'blank')


class TimeShiftMatcher:
    """Match rows against their delayed measurement in O(log n) per row.

    The sorted timestamp index is built once, so a preview that only varies the
    delay can reuse the same matcher instead of rescanning every row pair.
    """

    def __init__(self: Self, timestamps: list[datetime | None]) -> None:
        self.row_count = len(timestamps)
        self.target_times = [None if timestamp is None else timestamp.timestamp()
                             for timestamp in timestamps]
        ordered = sorted((epoch, row)
                         for row, epoch in enumerate(self.target_times)
                         if epoch is not None)
        # Where each row sits among the rows sharing its timestamp, see _row_at.
        self.block_offsets = [0] * self.row_count
        offset = 0
        for position, (epoch, row) in enumerate(ordered):
            if position and epoch != ordered[position - 1][0]:
                offset = 0
            self.block_offsets[row] = offset
            offset += 1
        self.epochs = [epoch for epoch, _ in ordered]
        self.row_indexes = [row for _, row in ordered]

    def source_indexes(self: Self, delay_seconds: float,
                       strategy: str = 'nearest',
                       tolerance_seconds: float = 1.0) -> list[int | None]:
        if strategy not in STRATEGIES:
            raise ValueError(f'Unknown time matching strategy: {strategy}')
        if tolerance_seconds < 0:
            raise ValueError('tolerance_seconds must not be negative')
        if strategy == 'blank' or not self.epochs:
            return [None] * self.row_count
        match = {'nearest': self._nearest, 'previous': self._previous,
                 'next': self._next}[strategy]
        indexes: list[int | None] = []
        for target_row, timestamp in enumerate(self.target_times):
            if timestamp is None:
                indexes.append(None)
                continue
            candidate = match(timestamp + delay_seconds, target_row)
            if candidate is None or candidate[0] > tolerance_seconds:
                indexes.append(None)
            else:
                indexes.append(candidate[1])
        return indexes

    def _row_at(self: Self, position: int, target_row: int) -> int:
        """Pick a row out of the rows sharing one timestamp.

        A logger writing several rows per second into a seconds-resolution
        format leaves whole blocks of rows on the exact same timestamp, every
        one of them equally close. Keeping the row's place within its own block
        maps the n:th sample of one second onto the n:th sample of the second it
        is shifted to, so the rows stay one to one instead of collapsing onto
        whichever row happened to open the second - and a zero delay maps every
        row onto itself.
        """
        epoch = self.epochs[position]
        start = bisect_left(self.epochs, epoch)
        end = bisect_right(self.epochs, epoch)
        if end - start == 1:
            return self.row_indexes[start]
        return self.row_indexes[start + min(self.block_offsets[target_row],
                                            end - start - 1)]

    def _nearest(self: Self, target_time: float,
                 target_row: int) -> tuple[float, int] | None:
        position = bisect_left(self.epochs, target_time)
        best = None
        # Two measurements the same distance apart on either side stay decided
        # by file order, only rows sharing one timestamp go by _row_at.
        for candidate in (position - 1, position):
            if candidate < 0 or candidate >= len(self.epochs):
                continue
            found = (abs(self.epochs[candidate] - target_time),
                     self._row_at(candidate, target_row))
            if best is None or found < best:
                best = found
        return best

    def _previous(self: Self, target_time: float,
                  target_row: int) -> tuple[float, int] | None:
        position = bisect_right(self.epochs, target_time)
        if position == 0:
            return None
        return (target_time - self.epochs[position - 1],
                self._row_at(position - 1, target_row))

    def _next(self: Self, target_time: float,
              target_row: int) -> tuple[float, int] | None:
        position = bisect_left(self.epochs, target_time)
        if position == len(self.epochs):
            return None
        return (self.epochs[position] - target_time,
                self._row_at(position, target_row))


def match_source_indexes(timestamps: list[datetime | None], delay_seconds: float,
                         strategy: str = 'nearest',
                         tolerance_seconds: float = 1.0) -> list[int | None]:
    """Row by row, point out which row holds its delayed measurement."""
    return TimeShiftMatcher(timestamps).source_indexes(
        delay_seconds, strategy, tolerance_seconds)


def shift_import_attributes(rows: list[list[str]], timestamps: list[datetime|None],
                            date_index: int, longitude_index: int,
                            latitude_index: int, delay_seconds: float,
                            strategy: str = 'nearest',
                            tolerance_seconds: float = 1.0
                            ) -> tuple[list[list[str]], list[int|None]]:
    """Copy delayed measurements onto original rows, preserving time/place."""
    if len(rows) != len(timestamps):
        raise ValueError('rows and timestamps must have equal length')
    source_indexes = match_source_indexes(timestamps, delay_seconds, strategy,
                                          tolerance_seconds)
    result = [row.copy() for row in rows]
    preserved = {date_index, longitude_index, latitude_index}
    columns_by_length: dict[int, list[int]] = {}
    for target_index, source_index in enumerate(source_indexes):
        target_row = result[target_index]
        columns = columns_by_length.get(len(target_row))
        if columns is None:
            columns = [column for column in range(len(target_row))
                       if column not in preserved]
            columns_by_length[len(target_row)] = columns
        if source_index is None:
            for column in columns:
                target_row[column] = ''
        else:
            source_row = rows[source_index]
            for column in columns:
                target_row[column] = source_row[column]
    return result, source_indexes
