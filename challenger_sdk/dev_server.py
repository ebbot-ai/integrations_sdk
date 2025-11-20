import sqlite3
import json
from datetime import datetime
from typing import override
from uuid import uuid4

from fastapi import HTTPException

from challenger_sdk.workflow import (
    Connection,
    Vars,
    WorkflowStorage,
    NewSubscription,
    Subscription,
    SubscriptionResult,
)


class DevServerWorkflowStorage(WorkflowStorage):
    @override
    def save_connection(self, options: Vars = None, secrets: Vars = None) -> Connection:
        cursor = init_dev_db()
        connection_id = str(uuid4())
        wf_server_id = str(uuid4())
        ts = datetime.now().isoformat() + "Z"
        cursor.execute(
            """
            INSERT INTO connections(id, wfServerId, secrets, options, createdAt, updatedAt)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                connection_id,
                wf_server_id,
                json.dumps(secrets or {}),
                json.dumps(options or {}),
                ts,
                ts,
            ),
        )
        cursor.connection.commit()
        cursor.close()
        return Connection(
            id=connection_id,
            wfServerId=wf_server_id,
            options=options or {},
            secrets=secrets or {},
            createdAt=ts,
            updatedAt=ts,
        )

    @override
    def get_connection(self, connectionId: str) -> Connection:
        cursor = init_dev_db()
        cursor.execute(
            """
            SELECT id, wfServerId, secrets, options, createdAt, updatedAt
            FROM connections
            WHERE id = ?
            """,
            (connectionId,),
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            raise HTTPException(404, detail="not found")
        secrets = json.loads(row[2]) if row[2] else {}
        options = json.loads(row[3]) if row[3] else {}
        return Connection(
            id=row[0],
            wfServerId=row[1],
            secrets=secrets,
            options=options,
            createdAt=row[4],
            updatedAt=row[5],
        )

    @override
    def save_subscription(
        self, connectionId: str, subscription: NewSubscription
    ) -> Subscription:
        cursor = init_dev_db()
        subscription_id = str(uuid4())
        ts = datetime.now().isoformat() + "Z"
        data = subscription.model_dump()
        cursor.execute(
            """
            INSERT INTO subscriptions(id, connectionId, data, createdAt, updatedAt)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                subscription_id,
                connectionId,
                json.dumps(data),
                ts,
                ts,
            ),
        )
        cursor.connection.commit()
        cursor.close()
        # Build Subscription model (assumes Subscription can accept these fields)
        data.update(
            {
                "id": subscription_id,
                "connectionId": connectionId,
                "createdAt": ts,
                "updatedAt": ts,
            }
        )
        return Subscription(**data)

    @override
    def get_subscription(self, subscriptionId: str) -> Subscription:
        cursor = init_dev_db()
        cursor.execute(
            """
            SELECT id, connectionId, data, createdAt, updatedAt
            FROM subscriptions
            WHERE id = ?
            """,
            (subscriptionId,),
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            raise HTTPException(404, detail="not found")
        data = json.loads(row[2]) if row[2] else {}
        data.update(
            {
                "id": row[0],
                "connectionId": row[1],
                "createdAt": row[3],
                "updatedAt": row[4],
            }
        )
        return Subscription(**data)

    @override
    def remove_subscription(self, connectionId: str, subscriptionId: str):
        cursor = init_dev_db()
        cursor.execute(
            """
            DELETE FROM subscriptions
            WHERE id = ?
            """,
            (subscriptionId,),
        )
        if cursor.rowcount == 0:
            cursor.close()
            raise HTTPException(404, detail="not found")
        cursor.connection.commit()
        cursor.close()

    @override
    def update_subscription(self, subscription: Subscription):
        cursor = init_dev_db()
        update_data = {}
        # Only update options / secrets if provided (allow clearing with empty dict)
        if subscription.options is not None:
            update_data["options"] = subscription.options
        if subscription.secrets is not None:
            update_data["secrets"] = subscription.secrets

        ts = datetime.now().isoformat() + "Z"
        cursor.execute(
            """
            UPDATE subscriptions
            SET data = ?, updatedAt = ?
            WHERE id = ?
            """,
            (
                json.dumps(update_data),
                ts,
                subscription.id,
            ),
        )
        if cursor.rowcount == 0:
            cursor.close()
            raise HTTPException(404, detail="not found")
        cursor.connection.commit()
        cursor.close()
        return Subscription(
            id=subscription.id,
            connectionId=subscription.connectionId,
            name=subscription.name,
            callback=subscription.callback,
            options=update_data.get("options"),
            secrets=update_data.get("secrets"),
        )

    @override
    def get_subscriptions(
        self, limit: int = 1000, offset: int = 0, name: str | None = None
    ):
        cursor = init_dev_db()
        params: list = []
        where = ""
        if name:
            where = "WHERE json_extract(data, '$.name') = ?"
            params.append(name)
        count_query = f"SELECT COUNT(*) FROM subscriptions {where}".strip()
        cursor.execute(count_query, tuple(params))
        total_row = cursor.fetchone()
        total = total_row[0] if total_row else 0
        query = f"""
            SELECT id, connectionId, data, createdAt, updatedAt
            FROM subscriptions
            {where}
            ORDER BY createdAt DESC
            LIMIT ? OFFSET ?
        """
        paginated_params = params + [limit, offset]
        cursor.execute(query, tuple(paginated_params))
        rows = cursor.fetchall()
        cursor.close()
        subs: list[Subscription] = []
        for row in rows:
            data = json.loads(row[2]) if row[2] else {}
            data.update(
                {
                    "id": row[0],
                    "connectionId": row[1],
                    "createdAt": row[3],
                    "updatedAt": row[4],
                }
            )
            subs.append(Subscription(**data))
        return SubscriptionResult(total=total, data=subs)

    @override
    def get_connection_subscriptions(
        self,
        connectionId: str,
        limit: int = 1000,
        offset: int = 0,
        name: str | None = None,
    ):
        cursor = init_dev_db()
        params: list = [connectionId]
        where = "WHERE connectionId = ?"
        if name:
            where += " AND json_extract(data, '$.name') = ?"
            params.append(name)
        count_query = f"SELECT COUNT(*) FROM subscriptions {where}".strip()
        cursor.execute(count_query, tuple(params))
        total_row = cursor.fetchone()
        total = total_row[0] if total_row else 0
        query = f"""
            SELECT id, connectionId, data, createdAt, updatedAt
            FROM subscriptions
            {where}
            ORDER BY createdAt DESC
            LIMIT ? OFFSET ?
        """
        paginated_params = params + [limit, offset]
        cursor.execute(query, tuple(paginated_params))
        rows = cursor.fetchall()
        cursor.close()
        subs: list[Subscription] = []
        for row in rows:
            data = json.loads(row[2]) if row[2] else {}
            data.update(
                {
                    "id": row[0],
                    "connectionId": row[1],
                    "createdAt": row[3],
                    "updatedAt": row[4],
                }
            )
            subs.append(Subscription(**data))
        return SubscriptionResult(total=total, data=subs)


def connect():
    con = sqlite3.connect("dev.db")
    return con.cursor()


def init_dev_db():
    cursor = connect()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS connections(
            id TEXT PRIMARY KEY,
            wfServerId TEXT,
            secrets TEXT,
            options TEXT,
            createdAt TEXT,
            updatedAt TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS subscriptions(
            id TEXT PRIMARY KEY,
            connectionId TEXT,
            data TEXT,
            createdAt TEXT,
            updatedAt TEXT
        )
        """
    )
    return cursor
