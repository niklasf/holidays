# -*- coding: utf-8 -*-

from PySide.QtCore import *

import uuid
import Queue
import threading
import mysql.connector


class MessageQueue(QObject):
    """The message queue."""

    received = Signal(int, str, str, str, str)

    def __init__(self, db):
        super(MessageQueue, self).__init__()

        self.db = db
        self.session = str(uuid.uuid4())
        self.queue = Queue.Queue()

        cursor = self.db.cursor()
        cursor.execute("SELECT MAX(id) FROM message_queue")
        self.last_id, = cursor.fetchone()

        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()

    def publish(self, channel, message, extra):
        """Publishes a message for other clients."""
        self.queue.put({
            "session": self.session,
            "channel": channel,
            "message": message,
            "extra": extra,
        })

    def run(self):
        """
        Keeps fetching updates from the message_queue table and fires the received signal
        accordingly.
        """
        while True:
            try:
                item = self.queue.get(True, 2)

                try:
                    cursor = self.db.cursor()
                    cursor.execute("INSERT INTO message_queue (session, channel, message, extra) VALUES (%(session)s, %(channel)s, %(message)s, %(extra)s)", item)
                except mysql.connector.Error:
                    self.queue.put(item)

            except Queue.Empty:
                pass
            finally:
                try:
                    if not self.db.is_connected():
                        self.db.reconnect(5, 10)

                    cursor = self.db.cursor()
                    cursor.execute("SELECT id, session, channel, message, extra FROM message_queue WHERE id > %(last_id)s AND session != %(session)s ORDER BY id ASC", {
                        "last_id": self.last_id,
                        "session": self.session,
                    })

                    for id, session, channel, message, extra in cursor:
                        self.received.emit(id, session, channel, message, extra)
                        self.last_id = id
                except mysql.connector.Error:
                    pass
