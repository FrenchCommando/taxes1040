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


def computation_2022(amount):
    if amount == 0:
        return 0
    if amount <= 170050:
        return amount * 0.24 - 6164.50
    if amount <= 215950:
        return amount * 0.32 - 19768.50
    if amount <= 539900:
        return amount * 0.35 - 26247.00
    return amount * 0.37 - 37045.00


def computation_2023(amount):
    if amount == 0:
        return 0  # not actually zero, but use the tables
    if amount <= 182_100:
        return amount * 0.24 - 6600.00
    if amount <= 231_250:
        return amount * 0.32 - 21168.00
    if amount <= 578_125:
        return amount * 0.35 - 28105.50
    return amount * 0.37 - 39668.00


def computation_2023_ny(amount):
    if amount <= 17_150:
        return amount * 0.04
    if amount <= 23_600:
        return 686 + (amount - 17_150) * 0.045
    if amount <= 27_900:
        return 976 + (amount - 23_600) * 0.0525
    if amount <= 161_550:
        return 1_202 + (amount - 27_900) * 0.0550
    if amount <= 323_200:
        return 8_553 + (amount - 161_550) * 0.06
    if amount <= 2_155_350:
        return 18_252 + (amount - 323_200) * 0.0685
    if amount <= 5_000_000:
        return 143_754 + (amount - 2_155_350) * 0.0965
    if amount <= 25_000_000:
        return 418_263 + (amount - 5_000_000) * 0.1030
    return 2_478_263 + (amount - 25_000_000) * 0.1090


def computation_2023_nyc(amount):
    # I mistakenly put head-of-household table instead of single
    if amount <= 21_600:
        return amount * 0.03078
    if amount <= 45_000:
        return 665 + (amount - 21_600) * 0.03762
    if amount <= 90_000:
        return 1_545 + (amount - 45_000) * 0.03819
    return 3_264 + (amount - 90_000) * 0.03876


def computation_2024(amount):
    if amount <= 11_600:
        return amount * 0.10
    if amount <= 47_150:
        return 1_160 + (amount - 11_700) * 0.12
    if amount <= 100_525:
        return 5_426 + (amount - 47_150) * 0.22
    if amount <= 191_950:
        return 17_168.50 + (amount - 100_525) * 0.24
    if amount <= 243_725:
        return 39_110.50 + (amount - 191_950) * 0.32
    if amount <= 609_350:
        return 55_678.50 + (amount - 243_725) * 0.35
    return 183_647.25 + (amount - 609_350) * 0.37


def computation_2024_ny(amount):
    # same comment as for NYC
    if amount <= 8_500:
        return amount * 0.04
    if amount <= 11_700:
        return 340 + (amount - 8_500) * 0.045
    if amount <= 13_900:
        return 484 + (amount - 11_700) * 0.05_25
    if amount <= 80_650:
        return 600 + (amount - 13_900) * 0.05_50
    if amount <= 215_400:
        return 4_271 + (amount - 80_650) * 0.06
    if amount <= 1_077_550:
        return 12_356 + (amount - 215_400) * 0.06_85
    if amount <= 5_000_000:
        return 71_413 + (amount - 1_077_550) * 0.09_65
    if amount <= 25_000_000:
        return 449_929 + (amount - 5_000_000) * 0.10_30
    return 2_509_929 + (amount - 25_000_000) * 0.10_90

def computation_2024_nyc(amount):
    # looks like it didn't change from previous year
    # but was the wrong table
    if amount <= 12_000:
        return amount * 0.03_078
    if amount <= 25_000:
        return 369 + (amount - 12_000) * 0.03_762
    if amount <= 50_000:
        return 858 + (amount - 25_000) * 0.03_819
    return 1_813 + (amount - 50_000) * 0.03_876
