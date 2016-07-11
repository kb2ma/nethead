#!/usr/bin/python
# Copyright 2014-2016, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0
'''
Entry point for Nethead Manager application. Starts HostManager.

Usage:
   $. ./manager.py
'''
import logging
log = logging.getLogger(__name__)

import os, pwd, random, sys
from   soscoap import ClientResponseCode
from   soscoap import CodeClass
from   soscoap import ServerResponseCode
from   soscoap import SuccessResponseCode
from   soscoap.server import CoapServer
from   models import Host
        
def getInvariantName(host):
    '''Provides a short string to name a host, based on host attributes that don't
    change.
    
    :param Host host: 
    :return:
    '''
    tail = host.address.split(':')[-1]
    name = 'mote-{0}'.format(tail)

class HostManager(object):
    '''
    Manages Nethead's network hosts. Uses an soscoap.CoapServer to send and receive 
    messages with hosts, and pynag to send NSCA messages to Nagios.
    '''
    def __init__(self, coapServer):
        self._coapServer = coapServer
        self._coapServer.registerForResourceGet(self._getResource)
        self._coapServer.registerForResourcePost(self._postResource)
        
        self._hosts = []
                
    def _getResource(self, resource):
        '''Sets the value in the provided resource, to satisfy a GET request.
        '''
        log.debug('GET resource path is {0}'.format(resource.path))
    
    def _postResource(self, resource):
        '''Records the value from the provided resource, from a POST request. 
        Creates Nagios host and service records if not found.
        
        Assumes the CoAP server handles any raised exception.
        
        Endpoints:
        
        - /nh/lo : Validates Nagios config storage for the mote with the source 
                   address of the packet -- a kind of registration to prepare 
                   for data messages.
        - /nh/rss: Reads JSON payload for RSS values with key of the neighbor 
                   whose address ends with the 4 hex chars (2 bytes), and value
                   of the RSS reading. 
        '''
        log.debug('POST resource path is {0}'.format(resource.path))
        if resource.path == '/nh/rss':
            log.warn('nh/rss path not implemented yet')
            
        elif resource.path == '/nh/lo':
            log.debug('/nh/lo: received from {0}'.format(resource.sourceAddress[0]))
            
            # Search for existing host record; create if none
            try:
                host = next(x for x in self._hosts if (x.address == resource.sourceAddress[0]))
            except StopIteration:
                host = None
            if not host:
                host = self._createHost(resource)
                if host:
                    self._hosts.append(host)
                    log.info('/nh/lo: Created host for {0}'.format(host.address))
                    resource.resultClass = CodeClass.Success
                    resource.resultCode  = SuccessResponseCode.Created
                else:
                    log.error('/nh/lo: Host creation failed for {0}'.format(resource.sourceAddress[0]))
                    resource.resultClass = CodeClass.ServerError
                    resource.resultCode  = ServerResponseCode.InternalServerError
            else:
                log.info('/nh/lo: Found host {0}'.format(host.name))
            
        else:
            log.warn('Unknown path: {0}'.format(resource.path))
            resource.resultClass = CodeClass.ClientError
            resource.resultCode  = ClientResponseCode.NotFound

    def _createHost(self, resource):
        '''Creates a host record for the mote described in the provided resource.
        
        :param resource: 
        :return: The created host
        :rtype: Host
        '''
        host = Host()
        host.interface_id = resource.value
        host.address      = resource.sourceAddress[0]
        host.name         = getInvariantName(host)    # requires ipAddress
        host.coords       = "100,100"                 # arbitrary values, so shows on map
        
        return host

    
if __name__ == "__main__":
    logging.basicConfig(filename='nethead.log', level=logging.DEBUG, 
                        format='%(asctime)s %(module)s %(message)s')
    log.info('Initializing Nethead server')

    formattedPath = '\n\t'.join(str(p) for p in sys.path)
    log.info('Running server with sys.path:\n\t{0}'.format(formattedPath))

    server = None
    try:
        coapServer = CoapServer()
        if coapServer:
            server = HostManager( coapServer )
            coapServer.start()
    except KeyboardInterrupt:
        pass
    except:
        log.exception('Catch-all handler for Nethead server')
