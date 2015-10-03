#!/usr/bin/python

import cookielib
import getpass
import os
import sys
import time
import urllib
import urllib2

from BeautifulSoup import BeautifulSoup


class iPay:
    PASSWORD_GATEWAY_URL = 'http://agateway.adp.com'
    ROOT_URL = 'https://ipay.adp.com'
    INDEX_URL = ROOT_URL + '/iPay/private/index.jsf'
    PAYCHECK_URL = ROOT_URL + '/iPay/private/listDoc.jsf'


class PayCheckFetcher:
    def __init__(self, username, password):
        password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(
            None,
            iPay.PASSWORD_GATEWAY_URL,
            username,
            password,
        )

        cookie_jar = cookielib.LWPCookieJar()

        o = urllib2.build_opener(
            urllib2.HTTPBasicAuthHandler(password_manager),
            urllib2.HTTPCookieProcessor(cookie_jar),
        )
        urllib2.install_opener(o)

    def _initialize(self):
        """
        We have to make an initial request so that the session cookie is
        properly updated and the child frames know that this is the parent
        (apparently, they don't look at the referrer).
        """
        self._get_response(url=iPay.INDEX_URL, soup=False)

    def _get_response(self, data=None, url=iPay.PAYCHECK_URL, soup=True):
        headers = {
            # pretend to be chrome so the jsf renders as i expect
            'User-Agent':
                'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_4; en-US) '
                'AppleWebKit/534.13 (KHTML, like Gecko) Chrome/9.0.597.19 '
                'Safari/534.13',
        }
        req = urllib2.Request(url, data, headers)
        response = urllib2.urlopen(req)

        return response if not soup else BeautifulSoup(response)

    def _get_inputs(self, soup):
        """
        Get the statement form's inputs as a dictionary
        """
        inputs = soup.find('form', id='statement').findAll('input')

        values = {input['name']: input['value']
                  for input in inputs if input['type'] == 'hidden'}

        # 0 is Pay Statements  (e.g. paychecks)
        # 5 is Pay Adjustments (e.g. RSUs)
        # 2 is W-2
        values[u'statement:changeStatementsType'] = 1

        return values

    def _get_all_years(self, soup):
        years = soup.find('span', id='statement:yearLinks').findAll('a')
        return {year.string: year['id'] for year in years if year is not None}

    def _get_paycheck_data(self, soup):
        checks = soup.find('table', id='statement:checks').findAll('tr')

        result = {}

        def date_key(t):
            key = (t.tm_year, t.tm_mon, t.tm_mday, 0)

            n = 1
            while key in result:
                key = (t.tm_year, t.tm_mon, t.tm_mday, n)
                n += 1

            return key

        for check in checks:
            checklink = check.find('a')
            if checklink:
                key = date_key(time.strptime(checklink.string, '%m/%d/%Y'))
                result[key] = checklink['id']
        return result

    def _download_file(self, url, filename):
        print '  > downloading {} to {}'.format(url, filename)

        filename = os.path.abspath(filename)

        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))

        with open(filename, 'wb') as fd:
            fd.write(self._get_response(url=url, soup=False).read())

    def _return_to_browse(self, soup):
        """
        Return to the 'browse' view so navigating to the next year works
        properly (this is needed because of their JSF)
        """
        inputs = self._get_inputs(soup)
        inputs['statement:done'] = 'statement:done'
        return self._get_response(urllib.urlencode(inputs))

    def request(self):
        """
        The public entry point that does all the magic and saves all the files
        """

        print 'Connecting to ADP...'

        self._initialize()
        soup = self._get_response()
        years = sorted(self._get_all_years(soup).items(), reverse=True)

        print 'Got years: [{}]'.format(', '.join([year[0] for year in years]))
        for year, year_id in years:
            print ' > processing {}'.format(year)

            inputs = self._get_inputs(soup)
            inputs[year_id] = year_id
            year_soup = self._get_response(urllib.urlencode(inputs))

            paychecks = sorted(
                self._get_paycheck_data(year_soup).items(),
                reverse=True
            )

            to_download = {}

            for date_key, date_id in paychecks:
                inputs = self._get_inputs(year_soup)
                inputs[date_id] = date_id

                filename = '{}/{}.pdf'.format(
                    date_key[0],
                    '-'.join(['{0:02d}'.format(k) for k in date_key]),
                )
                if os.path.exists(os.path.abspath(filename)):
                    """
                    TODO: to harden the check, the filename should also contain
                    the check number...
                    """
                    continue

                check_soup = self._get_response(urllib.urlencode(inputs))
                check_url = iPay.ROOT_URL + check_soup.iframe['src']
                to_download[filename] = check_url

            print ' > found {} checks in {}'.format(len(paychecks), year)
            print '  > {} paychecks already downloaded'.format(
                len(paychecks) - len(to_download.keys())
            )

            for filename, check_url in to_download.items():
                self._download_file(check_url, filename)

            soup = self._return_to_browse(year_soup)


def main(argv):
    if (len(argv) != 1 and len(argv) != 2):
        print "usage: python adp.py <username> [<password>]"
        return -1

    username = argv[0]
    password = argv[1] if len(argv) == 2 else getpass.getpass()

    try:
        PayCheckFetcher(username, password).request()
    except:
        raise  # uncomment to debug
        print 'There was an error somewhere...'
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
