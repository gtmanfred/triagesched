from collections import namedtuple
from datetime import datetime
from dateutil import parser
from flask import Flask, jsonify, request, url_for, Response
from flask_restful import Resource, Api
import os
from sqlite3 import connect

if bool(os.environ.get('DEBUG')) is True:
    conn = connect('users.db')
else:
    conn = connect('/usr/share/nginx/html/triagesched/users.db')
Columns = namedtuple('Columns', 'userid name ord triage enabled date')

app = Flask(__name__)
app.config["APPLICATION_ROOT"] = "/api/v1"
api = Api(app)


class User(Resource):
    def get(self, userid):
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM users WHERE userid="{userid}"')
        user = cursor.fetchone()
        if not user:
            return {'Error': f'Unable to find user: {userid}'}, 404
        return jsonify(Columns(*user)._asdict())

    def put(self, userid):
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM users WHERE userid="{userid}"')
        user = cursor.fetchone()
        if not user:
            return {'Error': f'Unable to find user: {userid}'}, 404
        user = Columns(*user)
        user._replace(**request.json)
        userid = user.userid
        for key, value in user._asdict().items():
            if key is 'userid':
                continue
            cursor.execute(f'UPDATE users SET {key}="{value}" where userid="{userid}";')
        ret = jsonify(Columns(*cursor.execute(f'SELECT * FROM users WHERE userid="{userid}";').fetchone()))
        ret.headers['Access-Control-Allow-Origin'] = '*'
        return ret
        
    def delete(self, userid):
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM users WHERE userid="{userid}"')
        user = cursor.fetchone()
        if not user:
            return {'Error': f'Unable to find user: {userid}'}, 404
        cursor.execute(f'DELETE FROM users WHERE userid="{userid}"')
        cursor.execute(f'SELECT * FROM users WHERE userid="{userid}"')
        user = cursor.fetchone()
        if user:
            return {'Error': 'Failed to delete: {userid}'}, 500
        return jsonify({'message': 'success'})

    def options(self, userid):
        ret = Response("")
        ret.headers['Access-Control-Allow-Origin'] = '*'
        ret.headers['Access-Control-Allow-Methods'] = 'PUT, GET, OPTIONS, DELETE'
        ret.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return ret


class Users(Resource):
    def get(self):
        cursor = conn.cursor()
        ret, enabled = {}, ''
        if 'enabled' in request.args:
            enabled = 'WHERE enabled=1 '
        search = f'SELECT * FROM users {enabled}ORDER BY ord;'
        for user in cursor.execute(search):
            ret.setdefault('users', []).append(Columns(*user)._asdict())
        if not ret:
            return {'Error': f'No users defined'}, 404
        ret = jsonify(ret)
        ret.headers['Access-Control-Allow-Origin'] = '*'
        return ret

    def post(self):
        name, ord_ = request.json['name'], request.json['ord']
        cursor = conn.cursor()
        cursor.execute(f'INSERT INTO users (name, ord) VALUES ("{name}", {ord_});')
        conn.commit()
        ret = jsonify(Columns(*cursor.execute(f'SELECT * FROM users WHERE name="{name}";').fetchone())._asdict())
        ret.headers['Access-Control-Allow-Origin'] = '*'
        return ret

    def options(self):
        ret = Response("")
        ret.headers['Access-Control-Allow-Origin'] = '*'
        ret.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
        ret.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return ret


class Triage(Resource):
    def get(self):
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM users WHERE triage=1')
        user = Columns(*cursor.fetchone())
        date = parser.parse(user.date).strftime('%A, %B %w, %Y')
        ret = jsonify({'triage': user.name, 'date': date})
        ret.headers['Access-Control-Allow-Origin'] = '*'
        return ret

    def put(self):
        cursor = conn.cursor()
        users = []
        search = f'SELECT * FROM users ORDER BY ord;'
        for user in cursor.execute(search):
            users.append(Columns(*user))
        nextuser = False
        for user in users:
            if user.triage == 1:
                cursor.execute(f'UPDATE users SET triage=0 WHERE userid={user.userid}')
                conn.commit()
                nextuser = True
            elif user.enabled == 0:
                continue
            elif nextuser is True:
                cursor.execute(f'UPDATE users SET triage=1, date="{datetime.now()}" WHERE userid={user.userid}')
                conn.commit()
                nextuser = False
                ret = {'nexttriage': user.name, 'date': user.date}
                break
        if nextuser is True:
            for user in users:
                if user.enabled == 1:
                    cursor.execute(f'UPDATE users SET triage=1, date="{datetime.now()}" WHERE userid={user.userid}')
                    conn.commit()
                    ret = {'nexttriage': user.name, 'date': user.date}
                    break
        return jsonify(ret)


prefix = '/api/v1'
api.add_resource(User, f'{prefix}/users/<string:userid>')
api.add_resource(Users, f'{prefix}/users')
api.add_resource(Triage, f'{prefix}/triage')

def make_app():
    c = conn.cursor()
    c.execute((
        'CREATE TABLE IF NOT EXISTS users ('
        'userid INTEGER PRIMARY KEY AUTOINCREMENT, '
        'name TEXT NOT NULL, '
        'ord INTEGER NOT NULL, '
        'triage BOOLEAN NOT NULL DEFAULT 0, '
        'enabled BOOLEAN NOT NULL DEFAULT 1, '
        'date datetime default current_timestamp);'
    ))
    conn.commit()
    return app

if __name__ == '__main__':
    make_app().run()
