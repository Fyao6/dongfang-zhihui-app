"""Global disclosure binding only. This module never creates provider receipts or sends data."""
import hashlib
import json
import re
from urllib.parse import urlsplit

SCENES = ('chat', 'chart', 'course', 'card')
PROTOCOL_SUFFIXES = {'responses': '/responses', 'anthropic_messages': '/messages', 'chat_completions': '/chat/completions'}


def _endpoint(value):
    try:
        if not isinstance(value, str) or any(c.isspace() for c in value):
            return ''
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            return ''
        host = parsed.hostname.lower()
        if ':' in host:
            host = '[' + host + ']'
        return 'https://' + host + ('' if parsed.port in (None, 443) else ':' + str(parsed.port)) + (parsed.path or '/')
    except (TypeError, ValueError):
        return ''


def _regions(value):
    if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x.strip() for x in value):
        return None
    return sorted(set(x.strip() for x in value))


def _policy_url(value):
    try:
        parsed = urlsplit(value)
        return parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password
    except (TypeError, ValueError):
        return False


def _ready(cfg):
    if not isinstance(cfg, dict) or not all(isinstance(cfg.get(k), str) and cfg[k].strip() for k in ('policyVersion', 'controllerName', 'contact')):
        return False
    recipients = cfg.get('recipients')
    if not isinstance(recipients, list) or not recipients:
        return False
    ids = []
    for r in recipients:
        if not isinstance(r, dict) or not all(isinstance(r.get(k), str) and r[k].strip() for k in ('id', 'name', 'purpose', 'policyUrl', 'endpoint')):
            return False
        if not _endpoint(r['endpoint']) or not _policy_url(r['policyUrl']) or _regions(r.get('regions')) is None:
            return False
        if not isinstance(r.get('models'), list) or not r['models'] or any(not isinstance(m, str) or not m.strip() for m in r['models']):
            return False
        ids.append(r['id'])
    return len(ids) == len(set(ids))


def _legacy_binding(cfg, legacy):
    """Compatibility fallback for standalone use; integration injects frozen actual_binding."""
    try:
        provider, endpoint, regions = legacy.get('providerId'), _endpoint(legacy.get('endpoint')), _regions(legacy.get('processingRegions'))
        receiver = next((r for r in cfg['recipients'] if r['id'] == provider), None)
        # Preserve the exact legacy digest schema and insertion order.
        if not receiver or not provider or not endpoint or not legacy.get('model') or regions is None:
            return None
        if not (cfg.get('policyVersion') and cfg.get('controllerName') and cfg.get('contact') and cfg.get('recipients') and all(r.get('id') and r.get('name') and r.get('regions') and r.get('purpose') and r.get('policyUrl') and r.get('endpoint') and r.get('models') for r in cfg['recipients'])):
            return None
        if endpoint != _endpoint(receiver.get('endpoint')) or legacy['model'] not in receiver.get('models', []) or regions != sorted(set(receiver['regions'])) or legacy.get('privacyPolicyVersion') != cfg['policyVersion']:
            return None
        fields = {'providerId': provider, 'endpoint': endpoint, 'model': legacy['model'], 'processingRegions': regions, 'privacyPolicyVersion': legacy['privacyPolicyVersion'], 'policyVersion': cfg['policyVersion'], 'receiverId': receiver['id']}
        return {'digest': hashlib.sha256(json.dumps(fields, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(), 'details': fields}
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def registry_binding(cfg, gateway):
    """Bind only providers actually referenced by server routes, with independent receipts still required."""
    try:
        if not _ready(cfg) or not isinstance(gateway, dict) or gateway.get('environment') != 'local-test':
            return None
        routes, providers = gateway.get('routes'), gateway.get('providers')
        if not isinstance(routes, dict) or set(routes) != set(SCENES) or not isinstance(providers, list):
            return None
        by_id = {}
        for p in providers:
            if not isinstance(p, dict) or not isinstance(p.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', p['id']) or p['id'] in by_id:
                return None
            by_id[p['id']] = p
        referenced = set()
        for route in routes.values():
            if not isinstance(route, dict) or set(route) != {'primary', 'fallback'} or not isinstance(route['primary'], str) or not isinstance(route['fallback'], list) or len(route['fallback']) > 3:
                return None
            fallback = route['fallback']
            if any(not isinstance(x, str) or not x for x in fallback) or len(fallback) != len(set(fallback)) or route['primary'] in fallback:
                return None
            referenced.update(([route['primary']] if route['primary'] else []) + fallback)
        if not referenced or not referenced.issubset(by_id):
            return None
        receipts = []
        for identifier in sorted(referenced):
            p = by_id[identifier]
            receiver = next((r for r in cfg['recipients'] if r['id'] == identifier), None)
            protocol, endpoint, regions = p.get('protocol'), p.get('endpoint'), _regions(p.get('processingRegions'))
            if not receiver or protocol not in PROTOCOL_SUFFIXES or not _endpoint(endpoint) or not urlsplit(endpoint).path.endswith(PROTOCOL_SUFFIXES[protocol]):
                return None
            # Match the gateway's actual per-provider receipt rules, not a display URL.
            if endpoint != receiver['endpoint'] or not isinstance(p.get('model'), str) or not p['model'].strip() or p['model'] not in receiver['models'] or regions is None or regions != sorted(set(receiver['regions'])) or p.get('privacyPolicyVersion') != cfg['policyVersion']:
                return None
            receipts.append({'providerId': identifier, 'protocol': protocol, 'endpoint': endpoint, 'model': p['model'], 'processingRegions': regions, 'privacyPolicyVersion': p['privacyPolicyVersion'], 'policyVersion': cfg['policyVersion'], 'receiverId': receiver['id']})
        details = {'mode': 'gateway-registry', 'schemaVersion': 1, 'policyVersion': cfg['policyVersion'], 'providers': receipts}
        canonical = json.dumps(details, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        return {'digest': hashlib.sha256(canonical.encode()).hexdigest(), 'details': details}
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def global_binding(cfg, legacy, gateway, legacy_binding=None):
    """Prefer a valid legacy binding unchanged; aggregate registry metadata only as fallback."""
    try:
        binding = (legacy_binding or _legacy_binding)(cfg, legacy)
    except (AttributeError, KeyError, TypeError, ValueError):
        binding = None
    return binding if binding else registry_binding(cfg, gateway)


def bridge_privacy_response(base, legacy, gateway, legacy_binding=None, account_id=None):
    """Pure adapter for the gateway's injected response hook; no preference/receipt writes."""
    if not isinstance(base, dict) or not isinstance(base.get('disclosure'), dict) or not isinstance(base.get('consents'), dict) or not isinstance(base.get('accountId'), str) or not base['accountId'] or account_id is not None and base['accountId'] != account_id:
        raise ValueError('A complete current-account privacy response is required')
    cfg = base['disclosure']
    binding = global_binding(cfg, legacy, gateway, legacy_binding)
    acknowledged = bool(binding and base.get('policyVersion') == cfg['policyVersion'] and base.get('providerBinding') == binding['digest'])
    disclosure = {**cfg, 'configured': bool(binding), 'providerBinding': binding['digest'] if binding else '', 'activeAI': binding['details'] if binding else None}
    return {**base, 'disclosure': disclosure, 'policyAcknowledged': acknowledged, 'consentEpoch': str(base['revision']) + ':' + cfg['policyVersion'] + ':' + (binding['digest'] if binding else ''), 'authorizedCategories': ['general', 'card'] + [k for k in ('chart', 'wellbeing') if base['consents'].get(k) is True] if acknowledged else []}
