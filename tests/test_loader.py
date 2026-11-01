"""Testes da T02: carregamento, tipos e normalização dos CSVs."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import date
from decimal import Decimal

import pytest

from emporio_agent.data.loader import DataLoadError, csv_path, load_all, normalize_email, normalize_phone


def _row(frame, column, value):
    rows = frame[frame[column] == value]
    assert len(rows) == 1
    return rows.iloc[0]


def test_row_counts(store_data):
    assert len(store_data.products) == 65
    assert len(store_data.categories) == 9
    assert len(store_data.promotions) == 25
    assert len(store_data.orders) == 20
    assert len(store_data.order_items) == 22
    assert len(store_data.customers) == 50


def test_product_types(store_data):
    product = _row(store_data.products, "product_id", 81)
    assert product.price_brl == Decimal("599.9")
    assert isinstance(product.price_brl, Decimal)
    assert isinstance(product.created_at, date)
    assert product.created_at == date(2021, 3, 15)
    assert isinstance(product.specs, dict)
    assert product.specs["top"] == "Spruce"
    assert all(isinstance(v, str) for p in store_data.products.specs for v in p.values())
    assert store_data.products["stock_quantity"].dtype == "int64"
    assert set(store_data.products.status) == {"active", "discontinued", "coming_soon"}


def test_product_has_category_name(store_data):
    assert _row(store_data.products, "product_id", 95).category_name == "Violões"
    assert _row(store_data.products, "product_id", 121).category_name == "Ukuleles"
    assert store_data.products.category_name.notna().all()


def test_promotion_is_active_is_bool(store_data):
    assert set(map(type, store_data.promotions.is_active)) == {bool}
    active = store_data.promotions[store_data.promotions.is_active]
    assert sorted(active.product_id) == [90, 94, 121, 127]


def test_order_types_and_empty_values(store_data):
    delivered = _row(store_data.orders, "order_id", 1)
    assert delivered.total_brl == Decimal("11499")
    assert delivered.order_date == date(2025, 10, 15)
    assert delivered.estimated_delivery == date(2025, 10, 25)
    assert delivered.tracking_code == "BRAB1234567BR"
    assert delivered.notes is None

    confirmed = _row(store_data.orders, "order_id", 9)
    assert confirmed.tracking_code is None
    assert confirmed.estimated_delivery is None
    assert confirmed.notes is None

    cancelled = _row(store_data.orders, "order_id", 19)
    assert cancelled.notes == "Pagamento não confirmado dentro do prazo"


def test_order_total_is_preserved_not_recalculated(store_data):
    # DATA_ANALYSIS Q3: o total registrado difere da soma a preço atual e deve ser mantido.
    assert _row(store_data.orders, "order_id", 3).total_brl == Decimal("3450")


def test_customer_normalization(store_data):
    customer = _row(store_data.customers, "customer_id", 1)
    assert customer.phone_digits == "67998123456"
    assert customer.email == "lucas.mendes@jmail.com"
    assert "phone" not in store_data.customers.columns


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("(67) 99812-3456", "67998123456"), ("67 99654-7821", "67996547821"), ("", "")],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_normalize_email():
    assert normalize_email("  Ana.Costa@Hayoo.com.BR ") == "ana.costa@hayoo.com.br"


def test_original_text_values_preserved(store_data, data_dir):
    with csv_path(data_dir, "products").open(encoding="utf-8", newline="") as handle:
        raw = {int(r["product_id"]): r for r in csv.DictReader(handle)}
    for product in store_data.products.itertuples(index=False):
        original = raw[product.product_id]
        assert product.name == original["name"]
        assert product.description == original["description"]
        assert product.specs == {k: str(v) for k, v in json.loads(original["specs"]).items()}
    assert "Fender" in _row(store_data.products, "product_id", 135).description


def _copy_data(data_dir, destination):
    destination.mkdir(parents=True)
    for path in data_dir.glob("*.csv"):
        shutil.copy2(path, destination / path.name)
    return destination


def test_works_with_spaces_and_accents_in_path(data_dir, tmp_path):
    copy = _copy_data(data_dir, tmp_path / "pasta com espaço e acentuação")
    assert len(load_all(copy).products) == 65


def test_missing_file_raises_clear_error(data_dir, tmp_path):
    copy = _copy_data(data_dir, tmp_path / "dados")
    csv_path(copy, "orders").unlink()
    with pytest.raises(DataLoadError, match="orders.csv"):
        load_all(copy)


def test_missing_column_raises_clear_error(data_dir, tmp_path):
    copy = _copy_data(data_dir, tmp_path / "dados")
    path = csv_path(copy, "customers")
    text = path.read_text(encoding="utf-8").replace("customer_id,name,phone,", "customer_id,name,", 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(DataLoadError, match=r"customers\.csv.*phone"):
        load_all(copy)


def test_invalid_value_reports_file_line_and_column(data_dir, tmp_path):
    copy = _copy_data(data_dir, tmp_path / "dados")
    path = csv_path(copy, "promotions")
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].rsplit(",", 1)[0] + ",talvez"
    path.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(DataLoadError, match=r"promotions\.csv, linha 2, coluna 'is_active'"):
        load_all(copy)


def test_loading_does_not_modify_original_files(data_dir):
    def snapshot():
        return {
            p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
            for p in sorted(data_dir.iterdir())
        }

    before = snapshot()
    load_all(data_dir)
    assert snapshot() == before
