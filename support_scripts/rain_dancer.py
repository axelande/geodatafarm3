import requests
import json


class MyRainDancer:
    def __init__(self, client='000001', username='Demo', password='Demo'):
        """Creates a Raindancer object with auth"""
        self.auth = "client={}&username={}&password={}".format(client, username, password)
        self.operations = None

    def get_operation_data(self):
        """Collects data from crops returns a list of list with guid and names for the crops"""
        self.operations = requests.get("http://portal.myraindancer.com/api/v1/operations?" + self.auth)
        test = json.loads(self.operations.text)
        try:
            data = test['data']
            return data
        except KeyError:
            return 'Failed'


if __name__ == "__main__":
    dancer = MyRainDancer()
    operations = dancer.get_operation_data()