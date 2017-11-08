#!/usr/bin/env python
import sys
import os
sys.path.append(os.path.join(os.path.abspath('.'), 'venv/lib/site-packages'))

from google.appengine.ext import vendor
# Add any libraries install in the "lib" folder.
vendor.add('lib')

import telegram
from flask import Flask, request
import core
import logging
from google.appengine.api import urlfetch
from google.appengine.ext import ndb

# Constants
RESPONSE_OK = "OK"
RESPONSE_FAIL = "FAIL"
STATUS_PENDING = 1
STATUS_AUTH = 0


class User(ndb.Model):
    chat_id = ndb.IntegerProperty()
    status = ndb.IntegerProperty()


def get_user(chat_id):
    query = User.query(User.chat_id == chat_id)

    query_list = list(query.fetch())

    if (len(query_list) == 1):
        # Old user
        logging.debug("User with chat_id %s found in data store", chat_id)
        return query_list[0]
    elif (len(query_list) > 1):
        # Query error
        logging.error("Multiple users for chat_id %s", chat_id)

        # Purge
        for user in query_list:
            user.key.delete()

        # Create new user
        user = User(chat_id=chat_id, status=STATUS_PENDING)
        user.put()

        return user
    else:
        # Create new user
        logging.info("Added new user with chat_id %s to datastore", chat_id)
        user = User(chat_id=chat_id, status=STATUS_PENDING)
        user.put()

        return user


def send_unlock_cmd(lock_host, lock_port, lock_code):
    logging.debug("Sending unlock request to %s %s", lock_host, lock_port)
    logging.info("Unlocking...")
    url = "http://" + lock_host + ":" + lock_port + "/unlock?code=" + lock_code
    try:
        result = urlfetch.fetch(url)
        if result.status_code == 200:
            logging.info("Unlock successful!")
            return True
        else:
            logging.info("Unlock failed!")
            return False
    except urlfetch.Error:
        logging.exception('Caught exception fetching url')

    return False


def handle_bot_msg(chat_id, command):

    logging.debug("Command from %s: %s", chat_id, command)

    user = get_user(chat_id)

    if user.status == STATUS_AUTH:
        if command == '/unlock':
            # Send unlock command
            bot.sendMessage(chat_id, "Unlocking...")
            unlock_result = send_unlock_cmd(app.config['LOCK_HOST'],
                                            app.config['LOCK_PORT'],
                                            app.config['LOCK_AUTHKEY'])
            # Check result
            if unlock_result:
                bot.sendMessage(chat_id, "Door is unlocked!")
            else:
                bot.sendMessage(chat_id, "Unlock failed!")
        elif command == "/logout":
            # User logout
            user.key.delete()
            bot.sendMessage(chat_id, "See you soon!")
        else:
            bot.sendMessage(chat_id, "Unknown command!")

    elif user.status == STATUS_PENDING:
        # Logging user
        if command == app.config['PASS']:
            # Update user status
            user.status = STATUS_AUTH
            user.put()

            # Send response
            bot.sendMessage(chat_id, "Password correct! Welcome :-)")
            logging.info("User %s added!", chat_id)
        else:
            user.key.delete()
            bot.sendMessage(chat_id, "Wrong password!")

    else:
        # Unknown user
        if command == "/login":
            # Update user status
            user.status = STATUS_PENDING
            user.put()

            bot.sendMessage(chat_id, "Please enter the password.")
        else:
            bot.sendMessage(chat_id, "You are not currently logged in!\nUse /login to start a session.")


app = Flask(__name__)
app.config.from_pyfile('bot.cfg', silent=True)

global bot
bot = telegram.Bot(token=app.config['BOT_TOKEN'])


@app.route(app.config['BOT_HOOK'], methods=['POST'])
def webhook_handler():
    if request.method == "POST":
        # retrieve the message in JSON and then transform it to Telegram object
        update = telegram.Update.de_json(request.get_json(force=True), bot)

        chat_id = update.message.chat.id

        # Telegram understands UTF-8, so encode text for unicode compatibility
        text = update.message.text.encode('utf-8')

        handle_bot_msg(chat_id, text)

        return RESPONSE_OK


@app.route('/set_webhook', methods=['GET', 'POST'])
def set_webhook():
    s = bot.setWebhook('https://' + app.config['HOST'] + app.config['BOT_HOOK'])
    if s:
        return RESPONSE_OK
    else:
        return RESPONSE_FAIL


@app.route('/ping', methods=['GET', 'POST'])
def ping_received():
    # Ping received
    return RESPONSE_OK


@app.route('/')
def index():
    return '.'
