import pytest
from unittest.mock import MagicMock, patch
from database import DatabaseHandler

@pytest.fixture
def db_handler():
    return DatabaseHandler("mongodb://test", "db", "col")

@patch('database.MongoClient')
def test_connect_success(mock_client, db_handler):
    mock_client.return_value.admin.command.return_value = {"ok": 1}
    assert db_handler.connect() is True
    assert db_handler.collection is not None

@patch('database.MongoClient')
def test_connect_fail(mock_client, db_handler):
    mock_client.side_effect = Exception("Conn Error")
    assert db_handler.connect() is False

def test_insert_one_not_connected(db_handler):
    assert db_handler.insert_one({"test": 1}) is False

def test_insert_one_success(db_handler):
    db_handler.collection = MagicMock()
    assert db_handler.insert_one({"test": 1}) is True
    db_handler.collection.insert_one.assert_called_once()

def test_insert_one_fail(db_handler):
    db_handler.collection = MagicMock()
    db_handler.collection.insert_one.side_effect = Exception("Insert Error")
    assert db_handler.insert_one({"test": 1}) is False

def test_delete_many_success(db_handler):
    db_handler.collection = MagicMock()
    db_handler.collection.delete_many.return_value.deleted_count = 5
    assert db_handler.delete_many({"test": 1}) == 5

def test_close(db_handler):
    db_handler.client = MagicMock()
    db_handler.close()
    db_handler.client.close.assert_called_once()
