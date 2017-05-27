from flask import Flask, jsonify, request, url_for
from flask_restful import Resource, Api
from json import dumps
import requests
from sqlite3 import connect

conn = connect('users.db')
cols = ('userid', 'name', 'ord', 'triage', 'enabled')

app = Flask(__name__)
api = Api(app)


def assemble(user):
    return dict(zip(cols, user))


class User(Resource):
    def get(self, userid):
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM users WHERE userid="{userid}"')
        user = cursor.fetchone()
        if not user:
            return {'Error': f'Unable to find user: {userid}'}, 404
        return jsonify(cursor.fetchone())

    def put(self, userid):
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM users WHERE userid="{userid}"')
        user = assemble(cursor.fetchone())
        if not user:
            return {'Error': f'Unable to find user: {userid}'}, 404
        user.update(request.json)
        userid = user.pop('userid')
        for key, value in user.items():
            cursor.execute(f'UPDATE users SET {key}="{value}" where userid="{userid}";')
        return assemble(cursor.execute(f'SELECT * FROM users WHERE userid="{userid}";').fetchone())
        

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


class Users(Resource):
    def get(self):
        cursor = conn.cursor()
        ret, enabled = {}, ''
        if 'enabled' in request.args:
            enabled = 'WHERE enabled=1 '
        search = f'SELECT * FROM users {enabled}ORDER BY ord;'
        for user in cursor.execute(search):
            ret.setdefault('users', []).append(assemble(user))
        if not ret:
            return {'Error': f'No users defined'}, 404
        return jsonify(ret)

    def post(self):
        name, ord_ = request.json['name'], request.json['ord']
        cursor = conn.cursor()
        cursor.execute(f'INSERT INTO users (name, ord) VALUES ("{name}", {ord_});')
        conn.commit()
        return assemble(cursor.execute(f'SELECT * FROM users WHERE name="{name}";').fetchone())


class Triage(Resource):
    def get(self):
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM users WHERE triage=1')
        return jsonify({'triage': assemble(cursor.fetchone())['name']})

    def put(self):
        cursor = conn.cursor()
        users = []
        search = f'SELECT * FROM users ORDER BY ord;'
        for user in cursor.execute(search):
            users.append(assemble(user))
        nextuser = False
        for user in users:
            if user['triage'] == 1:
                cursor.execute(f'UPDATE users SET triage=0 WHERE userid={user["userid"]}')
                conn.commit()
                nextuser = True
            elif user['enabled'] == 0:
                continue
            elif nextuser is True:
                cursor.execute(f'UPDATE users SET triage=1 WHERE userid={user["userid"]}')
                conn.commit()
                nextuser = False
                ret = {'nexttriage': user['name']}
                break
        print(nextuser)
        if nextuser is True:
            cursor.execute(f'UPDATE users SET triage=1 WHERE userid={users[0]["userid"]}')
            conn.commit()
            ret = {'nexttriage': users[0]['name']}
        return jsonify(ret)


api.add_resource(User, '/users/<string:userid>')
api.add_resource(Users, '/users')
api.add_resource(Triage, '/triage')

if __name__ == '__main__':
     c = conn.cursor()
     c.execute((
         'CREATE TABLE IF NOT EXISTS users ('
         'userid INTEGER PRIMARY KEY AUTOINCREMENT, '
         'name TEXT NOT NULL, '
         'ord INTEGER NOT NULL, '
         'triage BOOLEAN NOT NULL DEFAULT 0, '
         'enabled BOOLEAN NOT NULL DEFAULT 1);'
     ))
     app.run()