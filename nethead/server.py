#!/usr/bin/python
# Copyright (c) 2014, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0
'''
Core/Initial module for nethead monitoring.
'''
import logging
log = logging.getLogger(__name__)

import sys
from soscoap.server import CoapServer
import pynag.Plugins
import pynag.Utils

class Server(object):
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
        '''
        log.debug('POST resource path is {0}'.format(resource.path))
        if resource.path.startswith('/rss/') and len(resource.path) > 5:
            host     = resource.path[5:]
            
            # Submit RSS
            try:
                intValue = resource.value['s']
                pynag.Utils.send_nsca(pynag.Plugins.OK, 
                                      'Received RSS|rss={0}dBm;;;-100;-20'.format(intValue), 
                                      'localhost', 
                                      hostname=host, 
                                      service='rss')
                log.debug('sent nsca for hostname {0}, service {1}'.format(host, 'rss'))
            except KeyError:
                log.warn('No \'s\' key in rss payload')
            
            # Submit DAG rank
            try:
                intValue = resource.value['r']
            except KeyError:
                log.warn('No \'r\' key in rss payload')
            #logger.debug('[CoAP_Arbiter] intValue {0} for byte'.format(intValue))
            #text     = self._createCheckResult(host, 'DAG-rank', intValue)
            #self._submitCheck(text)
            
            #_np.add_perfdata('DAG-rank', intValue)
            #_np.send_nsca(OK, '', 'localhost', hostname=host, service='DAG-rank')
        else:
            log.debug('Unknown path')

    
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
            server = Server( coapServer )
            coapServer.start()
    except KeyboardInterrupt:
        pass
    except:
        log.exception('Catch-all handler for Nethead server')
