# Copyright 2020 MyOdoo.pl
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': 'Currency Rate Update - NBP',
    'version': '14.0.1.0.3',
    'author':
        'myOdoo.pl',
    'website': 'https://myodoo.pl',
    'license': 'AGPL-3',
    'category': 'Financial Management/Configuration',
    'summary': 'Provide NBP (National Bank of Poland) currency rates for OCA Currency Rate Update',
    'description': 
    """
    Provide NBP (National Bank of Poland) currency rates for OCA Currency Rate Update. 
    Provide support for 129 currencies.    
    
    """,
    'depends': [
        'base',
        'currency_rate_update'
    ],
    'data': [
        'views/res_currency_rate_provider_NBP.xml',
        'security/res_currency_rate_provider_nbp.xml'
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
}
