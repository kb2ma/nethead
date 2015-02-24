#!/usr/bin/python
# Copyright 2014-2015, Ken Bannister
# All rights reserved. 
#  
# Released under the Mozilla Public License 2.0, as published at the link below.
# http://opensource.org/licenses/MPL-2.0
'''
Entry point for Nethead Manager application. Starts HostManager.

Must start script as superuser; sets uid of this process to 'nagios' user. This 
user is required for access and interaction with Nagios.

Usage:
   #. ./manager.py
'''
import logging
log = logging.getLogger(__name__)

import os, pwd, random, sys
from   pynag.Model import Host, Service
import pynag.Plugins
import pynag.Utils
from   soscoap import ClientResponseCode
from   soscoap import CodeClass
from   soscoap import ServerResponseCode
from   soscoap import SuccessResponseCode
from   soscoap.server import CoapServer
        
def getInvariantName(host):
    '''Provides a short string to name a host, based on host attributes that don't
    change.
    
    :param Host host: Adagios host
    :return:
    '''
    return 'mote-{0}'.format(host.address[-4:])

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
            # Search for existing host record
            host  = None
            hosts = Host.objects.filter(address=resource.sourceAddress[0])
            if not hosts:
                log.error('/nh/rss: Host not found: {0}'.format(resource.sourceAddress[0]))
                resource.resultClass = CodeClass.ClientError
                resource.resultCode  = ClientResponseCode.PreconditionFailed
                return
            elif len(hosts) > 1:
                log.warn('Found {0} hosts; using the first one'.format(len(hosts)))

            host = hosts[0]
            
            for (nbrAddr,intValue) in resource.value.items():
                # Search for existing service record for this neighbor; create if none
                serviceName = 'rss-{0}'.format(nbrAddr)
                services    = Service.objects.filter(host_name=host.host_name, 
                                                     service_description=serviceName)
                service     = None
                if not services:
                    service = self._createRssService(host, nbrAddr)
                    if service:
                        log.info('/nh/rss: Created service {0} for host {1}'.format(service.service_description, 
                                                                                    service.host_name))
                        resource.resultClass = CodeClass.Success
                        resource.resultCode  = SuccessResponseCode.Created
                    else:
                        log.error('/nh/rss: Service creation failed for rss-{0} for host {1}'.format(nbrAddr, 
                                                                                                     host.host_name))
                        # How to notify that a *particular* service creation failed?
                        # Tally success and failure, and send some text back?
                        #resource.resultClass = CodeClass.ServerError
                        #resource.resultCode  = ServerResponseCode.InternalServerError
                        continue
                else:
                    if len(services) > 1:
                        log.warn('Found {0} services; using the first one'.format(len(services)))
                    service = services[0]
                
                # Submit RSS
                pynag.Utils.send_nsca(pynag.Plugins.OK, 
                                      'Received RSS|rss={0}dBm;;;-100;-20'.format(intValue), 
                                      'localhost', 
                                      hostname=host.host_name, 
                                      service=service.service_description)
                log.debug('Sent nsca for hostname {0}, service {1}'.format(host.host_name, 
                                                                           service.service_description))
            
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
            
        elif resource.path == '/nh/lo':
            log.debug('/nh/lo: received from {0}'.format(resource.sourceAddress[0]))
            
            if resource.sourceAddress[0][0:2] == '::':
                log.info('/nh/lo: Rejecting host address {0}'.format(resource.sourceAddress[0]))
                resource.resultClass = CodeClass.ClientError
                resource.resultCode  = ClientResponseCode.BadRequest
                return
            
            # Search for existing host record; create if none
            hosts = Host.objects.filter(address=resource.sourceAddress[0])
            if not hosts:
                host = self._createHost(resource.sourceAddress[0])
                if host:
                    log.info('/nh/lo: Created host {0}'.format(host.host_name))
                    resource.resultClass = CodeClass.Success
                    resource.resultCode  = SuccessResponseCode.Created
                else:
                    log.error('/nh/lo: Host creation failed for {0}'.format(resource.sourceAddress[0]))
                    resource.resultClass = CodeClass.ServerError
                    resource.resultCode  = ServerResponseCode.InternalServerError
            else:
                if len(hosts) > 1:
                    log.warn('Found {0} hosts; using the first one'.format(len(hosts)))
                log.info('/nh/lo: Found host {0}'.format(hosts[0].host_name))
            
        else:
            log.warn('Unknown path: {0}'.format(resource.path))
            resource.resultClass = CodeClass.ClientError
            resource.resultCode  = ClientResponseCode.NotFound

    def _createHost(self, ipAddress):
        '''Creates a Nagios host entry for the mote at the provided address.
        
        :param str ipAddress: IPv6 address of mote/host
        :return: The created host
        :rtype: Host
        '''
        host = Host()
        
        host.address                = ipAddress
        host.host_name              = getInvariantName(host)    # requires ipAddress
        host.active_checks_enabled  = 0
        host.check_interval         = 5                         # must define these two values,
        host.max_check_attempts     = 5                         # even though not used
        host.passive_checks_enabled = 1
        
        host.set_filename('/etc/nagios3/okconfig/hosts/{0}.cfg'.format(host.host_name))
        host.save()
        return host

    def _createRssService(self, host, nbrAddr):
        '''Creates a Nagios service entry for RSS readings for transmissiosn received 
        by a host from a particular neighbor. Saves the service configuration 
        in the file for the host, because Adagios uses this organization when
        adding a service in the UI.
        
        :param Host host: Adagios host
        :param str nbrAddr: Last four hex chars in neighbor address
        :return: The created service
        :rtype: Service
        '''
        service = Service()
        
        service.host_name              = host.host_name
        service.service_description    = 'rss-{0}'.format(nbrAddr)
        service.active_checks_enabled  = 0
        service.check_command          = 'return-ok'
        service.check_interval         = 1     # must define these two values,
        service.max_check_attempts     = 5     # even though not used
        service.passive_checks_enabled = 1
        
        service.set_filename('/etc/nagios3/okconfig/hosts/{0}.cfg'.format(getInvariantName(host)))
        service.save()
        return service

    def _genHelloPath(self):
        '''Generates a random 4 hex-char path to the registration data for a host.
        
        2014-12-30 Not used at present; retain as a template for any kind of token 
        generation.
        
        :return: str Path chars
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
    
    # Switch process uid to nagios user.
    pwdEntry = pwd.getpwnam('nagios')
    if pwdEntry:
        os.setuid(pwdEntry.pw_uid)
        log.info('Script uid set to user \'nagios\'')
    else:
        log.error('\'nagios\' user not found')
        sys.exit(-1)

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
