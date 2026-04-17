from __future__ import annotations

from typing import List

from src.adapters.base import RegistrarAdapter
from src.adapters.cloudflare import CloudflareAdapter
from src.adapters.generic import GenericRegistrarAdapter, RegistrarSpec
from src.adapters.godaddy import GoDaddyAdapter
from src.adapters.letshost import LetsHostAdapter
from src.adapters.namecheap import NamecheapAdapter
from src.availability_parser import KeywordRules
from src.request_runner import ProviderRuntimeConfig, RequestRunner


def _runtime(
    *,
    max_concurrency: int = 2,
    min_interval: float = 0.12,
    timeout: float = 10.0,
    retries: int = 2,
    cache_ttl: float = 20.0,
) -> ProviderRuntimeConfig:
    return ProviderRuntimeConfig(
        max_concurrency=max_concurrency,
        min_interval_seconds=min_interval,
        timeout_seconds=timeout,
        retries=retries,
        cache_ttl_seconds=cache_ttl,
    )


GENERIC_REGISTRAR_SPECS: list[RegistrarSpec] = [
    RegistrarSpec("domaincom", "Domain.com", "https://www.domain.com/domains/search/?searchTerm=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("namedotcom", "Name.com", "https://www.name.com/domain/search/[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("googledomains", "Google Domains (Squarespace)", "https://domains.google/?q=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("bluehost", "Bluehost", "https://www.bluehost.com/domains/search/?domainName=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("hostgator", "HostGator", "https://www.hostgator.com/domains/?search=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("dreamhost", "DreamHost", "https://www.dreamhost.com/domains/search/?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("ionos", "1&1 IONOS", "https://www.ionos.com/domains/domain-check?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("gandi", "Gandi.net", "https://shop.gandi.net/en/domain/search?query=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("namesilo", "NameSilo", "https://www.namesilo.com/domain/search?query=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("porkbun", "Porkbun", "https://porkbun.com/products/checkout/register?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("dynadot", "Dynadot", "https://www.dynadot.com/domain/search.html?searchTerm=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("hover", "Hover", "https://www.hover.com/domains/results?q=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("networksolutions", "Network Solutions", "https://www.networksolutions.com/domain-name-registration/[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("registercom", "Register.com", "https://www.register.com/domain/search-result?domainName=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("enom", "Enom", "https://www.enom.com/domains/search/?q=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("ovhcloud", "OVHcloud", "https://www.ovh.com/world/domains/search/?domainSearch=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("interserver", "InterServer", "https://www.interserver.net/search?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("bigrock", "BigRock", "https://www.bigrock.in/domains?search=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("hostinger", "Hostinger", "https://www.hostinger.com/domain-name-search?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("resellerclub", "ResellerClub", "https://www.resellerclub.com/domains/register-domain-name?domainName=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec(
        "alibabacloud",
        "Alibaba Cloud (Aliyun)",
        "https://www.alibabacloud.com/domain/checkresult?searchKey=[YOURDOMAIN]",
        runtime=_runtime(max_concurrency=1, min_interval=0.2),
    ),
    RegistrarSpec("reg123", "123 Reg", "https://www.123-reg.co.uk/domain-names/search-results/?search=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("eurodns", "EuroDNS", "https://www.eurodns.com/domain-registration/search?domainname=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("instra", "Instra", "https://www.instra.com/en/search?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("namebright", "NameBright", "https://www.namebright.com/search/domain-results?q=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("sav", "Sav", "https://www.sav.com/landing/domainsearch?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("domainmonster", "DomainMonster", "https://www.domainmonster.com/search/?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("domainpeople", "DomainPeople", "https://www.domainpeople.com/domains/search/?searchTerm=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("internetbs", "Internet.bs", "https://internetbs.net/domain.html?query=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("epik", "Epik", "https://www.epik.com/checkout/?search=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("rebel", "Rebel.com", "https://www.rebel.com/domain-availability/[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("iwantmyname", "iwantmyname", "https://iwantmyname.com/search?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("onlydomains", "OnlyDomains", "https://www.onlydomains.com/domain-name-registration?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("thexyz", "Thexyz", "https://thexyz.com/domain-registration/?s=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("dotster", "Dotster", "https://www.dotster.com/domain/search-results?domainName=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("joker", "Joker.com", "https://joker.com/#search?search=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec(
        "strato",
        "Strato",
        "https://www.strato.de/domains/domain-check/?q=[YOURDOMAIN]",
        runtime=_runtime(),
        rules=KeywordRules(
            available=("ist verfugbar", "ist verfügbar", "frei"),
            unavailable=("bereits vergeben", "nicht verfugbar", "nicht verfügbar"),
        ),
    ),
    RegistrarSpec("lcn", "LCN", "https://www.lcn.com/domains/search?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("uk2", "UK2", "https://www.uk2.net/domains/?search=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("mydomain", "MyDomain.com", "https://www.mydomain.com/domain-name-search/?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("namesco", "Names.co.uk (Namesco)", "https://www.names.co.uk/domain-names/search?search=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("tsohost", "Tsohost", "https://www.tsohost.com/domains/search?search=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("onamae", "GMO (Onamae)", "https://www.onamae.com/en/domain/search/?keyword=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("moniker", "Moniker", "https://www.moniker.com/domain/search?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("pananames", "Pananames", "https://www.pananames.com/domain/search?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("rrpproxy", "RRPproxy", "https://www.rrpproxy.net/domain-name-registration/?domain=[YOURDOMAIN]", runtime=_runtime()),
    RegistrarSpec("names007", "007Names", "https://www.007names.com/search?name=[YOURDOMAIN]", runtime=_runtime()),
]


def build_default_adapters(runner: RequestRunner, include_letshost: bool = True) -> List[RegistrarAdapter]:
    adapters: List[RegistrarAdapter] = [
        NamecheapAdapter(runner),
        GoDaddyAdapter(runner),
        CloudflareAdapter(runner),
    ]

    if include_letshost:
        adapters.append(LetsHostAdapter(runner))

    for spec in GENERIC_REGISTRAR_SPECS:
        adapters.append(GenericRegistrarAdapter(runner, spec))

    return adapters


__all__ = [
    "RegistrarAdapter",
    "RegistrarSpec",
    "GenericRegistrarAdapter",
    "NamecheapAdapter",
    "GoDaddyAdapter",
    "LetsHostAdapter",
    "CloudflareAdapter",
    "GENERIC_REGISTRAR_SPECS",
    "build_default_adapters",
]
