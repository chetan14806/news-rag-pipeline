"""Small, explicit domain vocabulary; these are entity types, never query answers.

Disambiguations were added after development-sample review. Keep that sample's
score separate from later review: vocabulary corrections are not general accuracy.
"""
import re

ORGANIZATIONS = {'Capgemini', 'Delhivery', 'Jupiter Money', '3i Partners', 'Forbes', 'LIC'}
NOT_ORGANIZATIONS = {'OpenShell', 'F404', 'Bengaluru Technology Centre',
                     'Revolutionary Innovation for Sustainable Engines', 'Aerospace',
                     'Permanent Labor Certification', 'Labor', 'Independent India'}
NOT_LOCATIONS = {'Viksit Bharat', 'Tejas', 'Indian Professionals'}
GENERIC_ORGANIZATIONS = {'group', 'company', 'organization', 'organisation', 'platform', 'business'}
INSTITUTION = re.compile(
    r'^(?:(?:IIT|IIM|NIT|IIIT|IISc)\s+[A-Z][\w.-]*(?:\s+[A-Z][\w.-]*){0,3}'
    r'|Indian Institute of (?:Technology|Management|Science)(?:\s+[A-Z][\w.-]*){0,3})$')


def platform_names(body):
    """Use explicit product descriptions; do not assume every powered city is an app."""
    names = set()
    for match in re.finditer(r'\b(?:technology|software|system)\s+powers\s+([^.;\n]{1,500}?)(?=,\s+which\b|[.;\n]|$)', body, re.I):
        following = body[match.end():match.end() + 500]
        if re.match(r'[^.!?\n]*[.!?]\s*(?:the|these)\s+(?:platforms|apps|products|services)\b', following, re.I):
            names.update(name.strip().casefold() for name in re.split(r',|\s+and\s+', match.group(1)) if name.strip())
    return names


def refine(values, evidence, body):
    values['companies'] = [v for v in values['companies'] if v not in NOT_ORGANIZATIONS and v.casefold() not in GENERIC_ORGANIZATIONS
                           and not re.search(r'\b(?:Founder|CEO|CIO|Anchor|Journalist|Product Showcase)\b', v, re.I)]
    values['locations'] = [v for v in values['locations'] if v not in NOT_LOCATIONS
                           and not re.search(r'http|www\.|\b(?:MD|Mn|realty)\b', v, re.I)]
    platforms = platform_names(body)
    locations = []
    for value in values['locations']:
        match = re.search(r'(?<!\w)' + re.escape(value) + r'(?!\w)', body, re.I)
        if INSTITUTION.fullmatch(value) and match:
            values['companies'].append(value)
            evidence.append({'field': 'companies', 'value': value, 'text': match.group(),
                             'start': match.start(), 'end': match.end(), 'label': 'institution_name_rule'})
        elif value.casefold() in platforms or re.search(r'\s+Operations$', value):
            if match:
                evidence.append({'field': 'locations', 'value': value, 'text': match.group(),
                                 'start': match.start(), 'end': match.end(),
                                 'label': 'non_geographic_context', 'excluded': True})
        else:
            locations.append(value)
    values['locations'] = locations
    # A merged phrase is not one company when both components already occur.
    names = {v.casefold() for v in values['companies']}
    values['companies'] = [v for v in values['companies'] if not (
        ' & ' in v and all(p.casefold() in names for p in v.split(' & ')))]
    for name in sorted(ORGANIZATIONS):
        for match in re.finditer(r'(?<!\w)' + re.escape(name) + r'(?!\w)', body):
            for field in values:
                values[field] = [v for v in values[field] if v.casefold() != name.casefold()]
            values['companies'].append(name)
            evidence.append({'field': 'companies', 'value': name, 'text': match.group(),
                             'start': match.start(), 'end': match.end(), 'label': 'reviewed_domain_vocabulary'})
    # Fund/company suffixes are useful disambiguators for model PERSON mistakes.
    for name in list(values['people']):
        if re.search(r'\b(?:Capital|Partners|Foundation|Retreat|Cafe|Café|Coffee|Ventures)\b', name):
            values['people'].remove(name)
            if name not in values['companies']:
                values['companies'].append(name)
            start = body.find(name)
            evidence.append({'field': 'companies', 'value': name, 'text': name,
                             'start': start, 'end': start+len(name), 'label': 'organization_suffix_rule'})
    for field in values:
        values[field] = sorted(set(values[field]), key=lambda value: (value.casefold(), value))
    return values, evidence
