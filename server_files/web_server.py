__author__ = 'Matrix'
import flask
from flask import Flask, request

from create_farm_rasp import CreateFarm
app = Flask(__name__)
#flask run --host=0.0.0.0
@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/create', methods=['POST'])
def create():
    username = request.form['username']
    password = request.form['password']
    farmname = request.form['farmname']
    print('creating database. user=%s, pass=%s, farm=%s' % (username, password, farmname))
    createFram = CreateFarm()
    text = createFram.check_data(farmname, username)
    if text != 'true, true, true':
        return text
    text = createFram.create_user_and_farm(farmname, username, password)
    return text



app.run(host='0.0.0.0')




