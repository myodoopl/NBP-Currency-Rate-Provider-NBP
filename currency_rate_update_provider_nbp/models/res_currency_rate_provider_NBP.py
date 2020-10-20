# Copyright 2020 MyOdoo.pl (https://myodoo.pl)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).


import logging
from collections import defaultdict
from datetime import timedelta, datetime
from odoo.exceptions import ValidationError
import requests

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

# API: http://api.nbp.pl/
# Calculate all currencies from all API tables
# Tables A, B - average Rates of currencies
# Table A - currencies update on working days between 11:45 and 12:15
# Table B - currencies update weekly on Wendesday between 11:45 and 12:15
# Table C - Buy and sell Rates of currencies. Update on working days between 7:45 and 8:15


class ResCurrencyRateProviderNBP(models.Model):
    _inherit = 'res.currency.rate.provider'

    service = fields.Selection(
        selection_add=[('NBP', 'National Bank of Poland')],
    )

    def _get_supported_currencies(self):
        self.ensure_one()
        if self.service != 'NBP':
            return super()._get_supported_currencies()  # pragma: no cover

        return \
            [
                # Table no. 1
                'THB', 'USD', 'AUD', 'HKD', 'CAD', 'NZD', 'SGD', 'EUR', 'HUF', 'CHF', 'GBP', 'UAH', 'JPY',
                'CZK', 'DKK', 'ISK', 'NOK', 'SEK', 'HRK', 'RON', 'BGN', 'TRY', 'ILS', 'CLP', 'PHP', 'MXN',
                'ZAR', 'BRL', 'MYR', 'RUB', 'IDR', 'INR', 'KRW', 'CNY', 'XDR',
                # Table no. 2
                'AFN', 'MGA', 'PAB', 'ETB', 'VES', 'BOB', 'CRC', 'SVC', 'NIO', 'GMD', 'MKD', 'DZD', 'BHD',
                'IQD', 'JOD', 'KWD', 'LYD', 'RSD', 'TND', 'MAD', 'AED', 'STN', 'BSD', 'BBD', 'BZD', 'BND',
                'FJD', 'GYD', 'JMD', 'LRD', 'NAD', 'SRD', 'TTD', 'XCD', 'SBD', 'ZWL', 'VND', 'AMD', 'CVE',
                'AWG', 'BIF', 'XOF', 'XAF', 'XPF', 'DJF', 'GNF', 'KMF', 'CDF', 'RWF', 'EGP', 'GIP', 'LBP',
                'SSP', 'SDG', 'SYP', 'GHS', 'HTG', 'PYG', 'ANG', 'PGK', 'LAK', 'MWK', 'ZMW', 'GEL', 'MDL',
                'ALL', 'HNL', 'SLL', 'SZL', 'LSL', 'AZN', 'MZN', 'NGN', 'ERN', 'TWD', 'TMT', 'MRU', 'TOP',
                'MOP', 'ARS', 'DOP', 'COP', 'CUP', 'UYU', 'BWP', 'GTQ', 'IRR', 'YER', 'QAR', 'OMR', 'SAR',
                'KHR', 'BYN', 'LKR', 'MVR', 'MUR', 'NPR', 'PKR', 'SCR', 'PEN', 'KGS', 'TJS', 'UZS', 'KES',
                'SOS', 'TZS', 'UGX', 'BDT', 'WST', 'KZT', 'MNT', 'VUV', 'BAM',
                # Manual
                'PLN'
            ]

    def _obtain_rates(self, base_currency, currencies, date_from, date_to):
        self.ensure_one()
        if self.service != 'NBP':
            return super()._obtain_rates(base_currency, currencies, date_from,
                                         date_to)  # pragma: no cover
        invert_calculation = False
        if base_currency != 'PLN':
            invert_calculation = True
            if base_currency not in currencies:
                currencies.append(base_currency)

        nbp_rate = NBPRatesHandler(currencies, date_from, date_to)
        nbp_calculated_tables = nbp_rate.json_request()

        if invert_calculation:

            for k in nbp_calculated_tables.keys():
                base_rate = float(nbp_calculated_tables[k][base_currency])
                for rate in nbp_calculated_tables[k].keys():
                    nbp_calculated_tables[k][rate] = str(float(base_rate / nbp_calculated_tables[k][rate]))
                nbp_calculated_tables[k]['PLN'] = str(1.0 * base_rate)

        _logger.debug(nbp_calculated_tables)
        return nbp_calculated_tables


class NBPRatesHandler:
    """
    Class that handle NBP Exchange Rates \n
    Currently handle Table A and Table B average currency
    """

    # API VALUES
    max_days_request = 93
    base_url = 'http://api.nbp.pl/api/exchangerates'
    tables = '/tables'
    rates = '/rates'
    table_A_url = '/A'
    table_B_url = '/B'
    table_C_url = '/C'
    format_json = '/?format=json'
    format_xml = '/?format=xml'

    def __init__(self, currencies, date_from, date_to):
        self.currencies = currencies
        self.date_from = date_from
        self.date_to = self.date_not_in_future(date_to)
        self.date_from_url = self.date_format_url(date_from)
        self.date_to_url = self.date_format_url(date_to)
        self.date_request_queue = self.create_request_queue()
        self.content = defaultdict(dict)

    def create_request_queue(self):
        """
        Create Array with ready requests dates
        If request is bigger than max_days_request then create separeted \n
        :return: Array [[url_date, url_date],...]
        """
        days_all = self.date_to - self.date_from
        days_all = days_all.days
        days_added = 0
        date_request_queue = []
        not_duplicate_flag = 0

        # Create array with start days and end days
        while True:
            days_tmp = self.max_days_request
            if (days_all - days_added) < self.max_days_request:
                days_tmp = days_all - days_added

            date_request_queue.append([
                self.date_format_url(self.date_from + timedelta(days=not_duplicate_flag) + timedelta(days=days_added)),
                self.date_format_url(
                    self.date_from + timedelta(days=not_duplicate_flag) + timedelta(days=days_added) + timedelta(
                        days=days_tmp))
            ])

            days_added = days_added + days_tmp
            not_duplicate_flag = 1
            if days_all == days_added:
                break

        return date_request_queue

    @staticmethod
    def date_format_url(date):
        """
        Format date to API string used in request \n
        :param date: date object
        :return: string
        """
        return date.strftime('%Y-%m-%d')

    def url_builder(self, *args):
        """
        Create url to request communication with API \n
        :param args: *args with parts of url
        :return: string
        """
        arg_url = ''
        for arg in args:
            if '/' in arg:
                arg_url = arg_url + arg
            else:
                arg_url = arg_url + '/' + arg
        return self.base_url + arg_url

    @staticmethod
    def find_last_wendesday(date):
        """
        Find nearest Wendesday before date \n
        :param date: date object
        :return: date object
        """
        while date.weekday() != 2:
            tmpdate = tmpdate - date.timedelta(days=1)
        return tmpdate

    def date_not_in_future(self, date):
        """
        Check if date is not in future \n
        If in future then change it to today date \n
        :param date: date object
        :return: date object
        """
        if date > date.today():
            return date.today()
        return date

    def json_request(self):
        """
        Make JSON request to API and handle it to return proper dict to module \n
        :param url: string
        """

        json_request_queue = []
        datequeue = self.create_request_queue()

        # Create Queue with full links to make GET request
        for date_search_start, date_search_end in datequeue:
            json_request_queue.append(
                self.url_builder(self.tables, self.table_A_url, date_search_start, date_search_end, self.format_json))
            json_request_queue.append(
                self.url_builder(self.tables, self.table_B_url, date_search_start, date_search_end, self.format_json))
        # Make GET requests
        for req_url in json_request_queue:
            r = requests.get(req_url)

            # Handle Errors
            if r.status_code == 404:
                _logger.warning('Error: %s - No data  for given time range' % r.text)
                raise ValidationError(
                    _('No data for given time range in NBP Currency Rate Provider')
                )
            if r.status_code == 400:
                _logger.error('Error: %s' % r.text)
                if len(r.text) > 20:
                    _logger.warning(
                        'Error: %s - Limit of 93 days has been exceeded in NBP Currency Rate Provider: %s ' % r.text % req_url)
                    raise ValidationError(
                        _('Limit of 93 days has been exceeded in NBP Currency Rate Provider %s - %s', req_url, )
                    )
                else:
                    _logger.warning(
                        'Error: %s - Bad format of request in NBP Currency Rate Provider: %s' % r.text % req_url)
                    raise ValidationError(
                        _('Bad format of request in NBP Currency Rate Provider')
                    )

            # Handle JSON
            r_body = r.json()
            for dic in r_body:
                dateq = dic['effectiveDate']
                dateq = datetime.strptime(dateq, '%Y-%m-%d')
                for curr in dic['rates']:
                    if curr['code'] in self.currencies:
                        self.content[dateq.isoformat()][curr['code']] = float(curr['mid'])
                # Static PLN Value
                self.content[dateq.isoformat()]['PLN'] = float(1.00)
            _logger.debug(self.content)
            return self.content
