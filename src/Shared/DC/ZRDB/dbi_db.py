##############################################################################
#
# Copyright (c) 2002 Zope Foundation and Contributors.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

import sys

import transaction

failures=0
calls=0

nonselect_desc=[
    ('Query',  'STRING', 62, 62, 0, 0, 1),
    ('Status', 'STRING', 12, 12, 0, 0, 1),
    ('Calls',  'STRING', 12, 12, 0, 0, 1),
    ]

class QueryError(Exception):
    pass

class DB:

    _p_oid=_p_changed=_registered=None

    defs={'STRING':'s', 'NUMBER':'n', 'DATE':'d'}

    def Database_Connection(self, string):
        # Create a dbi-compatible database connection
        raise NotImplemetedError(
            'attempt to create a database connection for an abstract dbi')

    Database_Error='Should be overriden by subclass'

    def __init__(self,connection):
        self.connection=connection
        db=self.db=self.Database_Connection(connection)
        self.cursor=db.cursor()

    def str(self,v, StringType=type('')):
        if v is None: return ''
        r=str(v)
        if r[-1:]=='L' and type(v) is not StringType: r=r[:-1]
        return r

    def __inform_commit__(self, *ignored):
        self._registered=None
        self.db.commit()

    def __inform_abort__(self, *ignored):
        self._registered=None
        self.db.rollback()

    def register(self):
        if self._registered: return
        transaction.get().register(self)
        self._registered=1


    def query(self,query_string, max_rows=9999999):
        global failures, calls
        calls=calls+1
        try:
            c=self.cursor
            self.register()
            queries=filter(None, [x.strip() for x in query_string.split('\0')])
            if not queries: raise QueryError('empty query')
            if len(queries) > 1:
                result=[]
                for qs in queries:
                    r=c.execute(qs)
                    if r is None: raise QueryError(
                        'select in multiple sql-statement query'
                        )
                    result.append((qs, str(`r`), calls))
                desc=nonselect_desc
            else:
                query_string=queries[0]
                r=c.execute(query_string)
                if r is None:
                    result=c.fetchmany(max_rows)
                    desc=c.description
                else:
                    result=((query_string, str(`r`), calls),)
                    desc=nonselect_desc
            failures=0
            c.close()
        except self.Database_Error as mess:
            c.close()
            self.db.rollback()
            failures=failures+1
            if ((mess.find(": invalid") < 0 and
                 mess.find("PARSE") < 0) or
                # DBI IS stupid
                mess.find(
                     "Error while trying to retrieve text for error") > 0
                or
                # If we have a large number of consecutive failures,
                # our connection is probably dead.
                failures > 100
                ):
                # Hm. maybe the db is hosed.  Let's try once to restart it.
                failures=0
                c.close()
                self.db.close()
                db=self.db=self.Database_Connection(self.connection)
                self.cursor=db.cursor()
                c=self.cursor
                c.execute(query_string)
                result=c.fetchall()
                desc=c.description
            else:
                raise sys.exc_info()

        if result:
            result='\n'.join(
                    map(
                        lambda row, self=self:
                        '\t'.join(map(self.str,row)),
                        result))+'\n'
        else:
            result=''

        return (
            "%s\n%s\n%s" % (
                '\t'.join(map(lambda d: d[0],desc)),
                '\t'.join(
                    map(
                        lambda d, defs=self.defs: "%d%s" % (d[2],defs[d[1]]),
                        desc)),
                result,
                )
            )
