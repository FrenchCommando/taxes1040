from utils.forms_constants import logger, override_keyword


def get_main_info(d):
    # gets name ssn address etc from w2

    # check that info matches between several W2
    keys_to_compare = {
        'FullName', 'FirstName', 'LastName',
        'Address', 'Address_apt',
        'Address_city', 'Address_state', 'Address_zip', 'SSN',
    }
    one_map = {}
    for w in d['W2']:
        for k in keys_to_compare:
            if k in w:
                val = w[k]
                if k in one_map:
                    vm = one_map[k]
                    if val != vm:
                        logger.error("Mismatch info between W2 - for key %s found %s and %s", k, val, vm)
                else:
                    one_map[k] = val
    for k in keys_to_compare:
        if k not in one_map:
            logger.error("Missing info from W2 %s", k)

    def split_name(full, first, last):
        s = full.split(" ")
        if len(s) == 2:
            i = ""
        else:
            i = s[1][0]
        return {'first_name': first, 'initial': i, 'last_name': last}

    info = {
        **split_name(one_map['FullName'], one_map['FirstName'], one_map['LastName']),
        'ssn': one_map['SSN'],
        'address_street_and_number': one_map['Address'],
        'address_apt': one_map['Address_apt'],
        'address_city_state_zip': " ".join([one_map['Address_city'], one_map['Address_state'], one_map['Address_zip']]),
    }

    if override_keyword in d:
        info.update(d[override_keyword])
    return info


def computation_2018(amount):
    if amount == 0:
        return 0
    if amount <= 157500:
        return amount * 0.24 - 5710.50
    if amount <= 200000:
        return amount * 0.32 - 18310.50
    if amount <= 500000:
        return amount * 0.35 - 24310.50
    return amount * 0.37 - 34310.50


def computation_2019(amount):
    if amount == 0:
        return 0
    if amount <= 160725:
        return amount * 0.24 - 5825.50
    if amount <= 204100:
        return amount * 0.32 - 18683.50
    if amount <= 510300:
        return amount * 0.35 - 24806.50
    return amount * 0.37 - 35012.50


def computation_2020(amount):
    if amount == 0:
        return 0
    if amount <= 163300:
        return amount * 0.24 - 5920.50
    if amount <= 207350:
        return amount * 0.32 - 18984.50
    if amount <= 518400:
        return amount * 0.35 - 25205
    return amount * 0.37 - 35573


def computation_2021(amount):
    if amount == 0:
        return 0
    if amount <= 164925:
        return amount * 0.24 - 5979.00
    if amount <= 209425:
        return amount * 0.32 - 19173.00
    if amount <= 523600:
        return amount * 0.35 - 25455.75
    return amount * 0.37 - 35927.75
