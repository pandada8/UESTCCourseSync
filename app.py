from flask import Flask, render_template, request
import model
from datetime import datetime
import os
import json

app = Flask(__name__)


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/add_to_list', methods=["POST"])
def AddToQueue():
    # save the data to the database
    if set(request.form) >= set(['username', 'password', 'mail']):
        with model.db.transaction():
            model.Task.create(
                create_time=datetime.now(),
                username=request.form.get('username'),
                password=request.form.get('password'),
                mail=request.form.get('mail'),
            )
            return render_template('waiting.html')
    return json.dumps({"msg": "Finished"})

app.secret_key = os.urandom(12)


if __name__ == "__main__":
    app.secret_key = "123456"  # easy for debuging
    app.debug = True
    app.run()
