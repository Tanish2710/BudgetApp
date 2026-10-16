"""Checks for the database, money and login logic. Run with: python -m pytest tests"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def app(tmp_path, monkeypatch):
    import database as db
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    import auth
    import logic
    return db, logic, auth


def test_allocate_amounts_adds_up_to_the_cent(app):
    db, _, _ = app
    assert db.allocate_amounts(100, [1, 1, 1]) == [33.34, 33.33, 33.33]
    assert round(sum(db.allocate_amounts(0.05, [1, 1, 1])), 2) == 0.05
    assert db.allocate_amounts(4800, [1, 2, 1, 2]) == [800.0, 1600.0, 800.0, 1600.0]


def test_balances_net_to_zero_and_settlements_clear_them(app):
    db, logic, _ = app
    a = db.create_user("A", "a@x.com")
    b = db.create_user("B", "b@x.com")
    c = db.create_user("C", "c@x.com")
    g = db.create_group("Flat")
    for u in (a, b, c):
        db.add_member_to_group(g, u)
    db.add_shared_expense(g, a, 90, "Groceries")
    bal = logic.compute_balances(g)
    assert bal == {a: 60.0, b: -30.0, c: -30.0}
    assert sorted(logic.simplify_debts(bal)) == sorted([(b, a, 30.0), (c, a, 30.0)])
    db.add_settlement(b, a, 30, g)
    assert logic.compute_balances(g)[b] == 0
    assert logic.compute_balances(None, []) == {}


def test_first_account_is_admin_and_later_ones_are_users(app):
    db, _, auth = app
    _, role1 = db.create_account("One", "one@x.com", auth.hash_password("abc12345"))
    _, role2 = db.create_account("Two", "two@x.com", auth.hash_password("abc12345"))
    assert (role1, role2) == ("admin", "user")
    with pytest.raises(ValueError):
        db.create_account("Again", "ONE@x.com", auth.hash_password("abc12345"))


def test_deleting_an_account_whose_circle_name_the_admin_already_uses(app):
    db, _, _ = app
    admin, _ = db.create_account("Admin", "admin@x.com", "h")
    bob, _ = db.create_account("Bob", "bob@x.com", "h")
    db.create_group("Trip", owner_id=admin)
    db.create_group("Trip", owner_id=bob)
    db.delete_account(bob, admin)
    assert sorted(g["group_name"] for g in db.get_all_groups()) == ["Trip", "Trip (from Bob)"]
    db.create_group("Later", owner_id=admin)  # the database isn't left locked


def test_renaming_a_circle_to_an_existing_name_in_other_case_is_refused(app):
    db, _, _ = app
    db.create_group("Goa Trip", owner_id=1)
    flat = db.create_group("Flat", owner_id=1)
    with pytest.raises(ValueError):
        db.rename_group(flat, "goa trip")
    db.create_group("Goa Trip", owner_id=2)  # other owners may reuse a name
    db.rename_group(flat, "Flat 302")
    assert db.get_group(flat)["group_name"] == "Flat 302"


def test_new_password_signs_out_other_sessions(app):
    db, _, auth = app
    uid, _ = db.create_account("Pat", "pat@x.com", auth.hash_password("abc12345"))
    here, elsewhere = auth.start_session(uid), auth.start_session(uid)
    assert auth.change_password(uid, "abc12345", "xyz98765", "xyz98765", keep_token=here) is None
    assert auth.account_for_token(here)["user_id"] == uid
    assert auth.account_for_token(elsewhere) is None
    db.set_password_hash(uid, auth.hash_password("reset1234"))  # an admin reset signs out everywhere
    assert auth.account_for_token(here) is None
    assert auth.log_in("pat@x.com", "reset1234")[1] is None


def test_password_rules_and_login(app):
    db, _, auth = app
    assert auth.password_problem("short1")
    assert auth.password_problem("onlyletters")
    assert auth.password_problem("abc12345", "abc12346")
    assert auth.password_problem("abc12345", "abc12345") is None
    db.create_account("Pat", "pat@x.com", auth.hash_password("abc12345"))
    assert auth.log_in("PAT@x.com ", "abc12345")[1] is None
    assert auth.log_in("pat@x.com", "wrong1234")[0] is None
