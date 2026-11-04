"""Confiança no proxy: o backend só aceita X-Forwarded-For do IP fixo do nginx (compose.yaml).

Integração com o mesmo middleware que o uvicorn aplica no contêiner (ProxyHeadersMiddleware, com
FORWARDED_ALLOW_IPS), sobre a API real e o limite de criação de sessões por cliente. Sem rede e
sem provedor de IA.
"""

from __future__ import annotations

import ipaddress
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from emporio_agent.api.app import create_app
from emporio_agent.config import REPO_ROOT, Settings

from fakes import FakeLLM

COMPOSE = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
MONDAY = datetime(2026, 11, 2, 10, 0, tzinfo=ZoneInfo("America/Campo_Grande"))
# 10/min com rajada de 5: 6 criações passam de imediato, a 7ª é barrada.
ALLOWED_AT_ONCE = 6


def _compose_value(key: str) -> str:
    match = re.search(rf"^\s*(?:-\s*)?{key}:\s*\"?([^\"\s#]+)\"?", COMPOSE, re.MULTILINE)
    assert match, f"{key} não encontrado no compose.yaml"
    return match.group(1)


TRUSTED = _compose_value("FORWARDED_ALLOW_IPS")
NGINX_IP = _compose_value("ipv4_address")
SUBNET = ipaddress.ip_network(_compose_value("subnet"))
IP_RANGE = ipaddress.ip_network(_compose_value("ip_range"))
# Gateway da rede: origem do que entra pela porta publicada no host. Com ip_range, o Docker usa o
# primeiro endereço da faixa (validado: 172.30.240.128); o .1 da sub-rede fica como alternativa.
GATEWAYS = [str(IP_RANGE.network_address), str(next(SUBNET.hosts()))]


class Clock:
    t = 1000.0

    def __call__(self) -> float:
        return self.t


def _client(tmp_path, peer: str) -> TestClient:
    app = create_app(
        Settings(runtime_dir=tmp_path, reference_datetime=MONDAY), llm=FakeLLM([]), env={}, clock=Clock()
    )
    # Igual ao uvicorn no contêiner: proxy_headers ligado com FORWARDED_ALLOW_IPS do compose.
    return TestClient(ProxyHeadersMiddleware(app, trusted_hosts=TRUSTED), client=(peer, 40000))


def _create(client: TestClient, forwarded_for: str) -> int:
    return client.post("/api/sessions", headers={"X-Forwarded-For": forwarded_for}).status_code


def test_compose_confia_somente_no_ip_fixo_do_nginx():
    assert TRUSTED != "*" and "," not in TRUSTED and "/" not in TRUSTED
    assert TRUSTED == NGINX_IP
    nginx = ipaddress.ip_address(NGINX_IP)
    assert nginx in SUBNET
    # Endereços automáticos (backend, gateway) não podem coincidir com o IP reservado ao nginx.
    assert nginx not in IP_RANGE and IP_RANGE.subnet_of(SUBNET)
    assert all(ipaddress.ip_address(g) != nginx for g in GATEWAYS)


@pytest.mark.parametrize("peer", [*GATEWAYS, "172.30.240.129", "203.0.113.7"])
def test_origem_nao_confiavel_nao_escolhe_o_ip_pelo_cabecalho(tmp_path, peer):
    # Forjar um X-Forwarded-For diferente a cada pedido não cria orçamentos novos: vale o peer.
    client = _client(tmp_path, peer)
    codes = [_create(client, f"10.0.0.{i}") for i in range(ALLOWED_AT_ONCE + 2)]
    assert codes == [201] * ALLOWED_AT_ONCE + [429, 429]


def test_nginx_confiavel_repassa_o_ip_real_de_cada_cliente(tmp_path):
    client = _client(tmp_path, NGINX_IP)
    # Clientes distintos atrás do nginx têm orçamentos independentes...
    assert [_create(client, f"198.51.100.{i}") for i in range(ALLOWED_AT_ONCE + 2)] == [201] * (ALLOWED_AT_ONCE + 2)
    # ...e o mesmo cliente continua limitado.
    codes = [_create(client, "198.51.100.250") for _ in range(ALLOWED_AT_ONCE + 1)]
    assert codes == [201] * ALLOWED_AT_ONCE + [429]
