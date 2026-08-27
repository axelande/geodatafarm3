"""Database-facing orchestration for the fertility-index calculation."""
from ..support_scripts import field_grid
from .fertility_index import classify_index, combine_sources


def source_values(db, field_name, source):
    """Read one numeric source value per grid cell for a selected field."""
    schema, table, attribute = source
    columns = db.get_all_columns(table, schema)
    geometry = 'polygon' if 'polygon' in columns else 'pos'
    rows = field_grid.join_grid_to_table(
        db, schema, table, [attribute], geometry_column=geometry)
    totals = {}
    for row in rows:
        value = row[attribute]
        if value is not None:
            cell_id = row['cell_id']
            total, count = totals.get(cell_id, (0.0, 0))
            totals[cell_id] = (total + float(value), count + 1)
    return {cell_id: total / count for cell_id, (total, count) in totals.items()}


def calculate_fertility_index(db, field_name, sources, weights=None,
                              boundaries=None, class_count=5):
    """Build the field grid and return cells with index and class values."""
    cells = field_grid.build_grid(db, field_name)
    if not cells:
        return []
    values_by_source = [source_values(db, field_name, source) for source in sources]
    names = [f'{source[0]}.{source[1]}.{source[2]}' for source in sources]
    aligned = {name: [source_values_map.get(cell.cell_id)
                      for cell in cells]
               for name, source_values_map in zip(names, values_by_source)}
    index_values = combine_sources(aligned, weights)
    classes = classify_index(index_values, boundaries, class_count)
    return [(cell, index, class_number)
            for cell, index, class_number in zip(cells, index_values, classes)]


def drop_fertility_grid(db):
    field_grid.drop_grid(db)