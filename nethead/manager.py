#!/usr/bin/python
# Copyright (c) 2014, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0
'''
Entry point for Nethead Manager application. Starts HostManager.

Usage:
   #. ./manager.py
'''
import logging
log = logging.getLogger(__name__)

import sys
from   pynag.Model import Host
import pynag.Plugins
import pynag.Utils
from   soscoap import ClientResponseCode
from   soscoap import CodeClass
from   soscoap import ServerResponseCode
from   soscoap import SuccessResponseCode
from   soscoap.server import CoapServer
import random

class HostManager(object):
    '''
    Manages Nethead's network hosts. Uses an soscoap.CoapServer to send and receive 
    messages with hosts, and pynag to send NSCA messages to Nagios.
    '''
    def __init__(self, coapServer):
        self._coapServer = coapServer
        self._coapServer.registerForResourceGet(self._getResource)
        self._coapServer.registerForResourcePost(self._postResource)
                
    def _getResource(self, resource):
        '''Sets the value in the provided resource, to satisfy a GET request.
        '''
        log.debug('GET resource path is {0}'.format(resource.path))
    
    def _postResource(self, resource):
        '''Records the value from the provided resource, from a POST request.
        
        Endpoints:
        
        - /nh/lo : Validates Nagios config storage for the mote with the source 
                   address of the packet -- a kind of registration to prepare 
                   for data messages.
        - /nh/rss: Reads JSON payload for RSS value at 's' key, with the neighbor 
                   whose address ends with the 4 hex chars (2 bytes) at 'n' key. 
        '''
        log.debug('POST resource path is {0}'.format(resource.path))
        if resource.path == '/nh/rss':
            # Search for existing host record
            hosts = Host.objects.filter(address=resource.sourceAddress[0])
            if not hosts:
                log.error('/nh/rss: Host not found: {0}', resource.sourceAddress)
                resource.resultClass = CodeClass.ClientError
                resource.resultCode  = ClientResponseCode.PreconditionFailed
                return
            elif len(hosts) > 1:
                log.warn('Found {0} hosts; using the first one'.format(len(hosts)))
                
            host = hosts[0]
            
            # Submit RSS
            try:
                nbrAddr  = resource.value['n']
                intValue = resource.value['s']
                pynag.Utils.send_nsca(pynag.Plugins.OK, 
                                      'Received RSS|rss={0}dBm;;;-100;-20'.format(intValue), 
                                      'localhost', 
                                      hostname=host.host_name, 
                                      service='rss')
                log.debug('Sent nsca for hostname {0}, service {1} (neighbor {2})'.format(host, 'rss', nbrAddr))
            except KeyError:
                log.error('/nh/rss: Missing \'n\' or \'s\' key in payload')
                resource.resultClass = CodeClass.ClientError
                resource.resultCode  = ClientResponseCode.BadRequest
            
            # Submit DAG rank
            #try:
            #    intValue = resource.value['r']
            #except KeyError:
            #    log.error('/nh/rss: No \'r\' key in payload')
            #    raise
            #logger.debug('[CoAP_Arbiter] intValue {0} for byte'.format(intValue))
            #text     = self._createCheckResult(host, 'DAG-rank', intValue)
            #self._submitCheck(text)
            
            #_np.add_perfdata('DAG-rank', intValue)
            #_np.send_nsca(OK, '', 'localhost', hostname=host, service='DAG-rank')
            
        elif resource.path == ('/nh/lo'):
            log.debug('/nh/lo: received from {0}'.format(resource.sourceAddress[0]))
            
            # Search for existing host record
            hosts = Host.objects.filter(address=resource.sourceAddress[0])
            if not hosts:
                # TODO If not found, add new host and service records
                log.info('/nh/lo: Created')
                resource.resultClass = CodeClass.Success
                resource.resultCode  = SuccessResponseCode.Created
            
        else:
            log.warn('Unknown path: {0}'.format(resource.path))
            resource.resultClass = CodeClass.ClientError
            resource.resultCode  = ClientResponseCode.NotFound

    def _createHelloPath(self):
        '''Creates a random 4 hex-char path to the registration data for a host
        
        2014-12-30 Not used at present; retain as a template for any kind of token 
        generation.
        
        :returns: str Path chars
        '''
        pathInt = random.randint(0, 0xFFFF)
        
        if Host.objects.filter(_uri_path=pathInt):
            for nextInt in range(pathInt+1, 0xFFFF):
                if not Host.objects.filter(_uri_path=nextInt):
                    pathInt = nextInt
                    break
            else:
                for nextInt in range(0, pathInt-1):
                    if not Host.objects.filter(_uri_path=nextInt):
                        pathInt = nextInt
                        break
                else:
                    log.error('Can''t generate host hello path')
                    raise KeyError

        return pathInt

    
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
