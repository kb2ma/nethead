#!/usr/bin/python
# Copyright 2014-2016, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0
'''
Models for Nethead Manager application.
'''
import logging
log = logging.getLogger(__name__)


class Host(object):
    '''
    A monitored host.
    '''
    def __init__(self):
        interface_id = None
        address      = None
        name         = None
        coords       = None
