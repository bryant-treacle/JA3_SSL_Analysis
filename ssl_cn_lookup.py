from datetime import datetime
from elasticsearch import Elasticsearch
import time
es = Elasticsearch()

#####################################################
# Create an empty table to place the unique results #
#####################################################
CN_NAME_UNIQUE = []

###################
# Start the loop  #
###################
while True:

#############################################################
# Elasticsearch Query to get All Common Names for SSL Certs #
#############################################################
    CN_NAME_SEARCH = es.search(index="*:logstash-*", body={"query": {"bool": {"must": [{"term" : {"event_type": "bro_ssl"}}], "filter": [{ "range": {"@timestamp": {"gte": "now-36h", "lte": "now"}}}]}}}, filter_path=['hits.hits._source.certificate_common_name'], size=10000)
#Example of the returned results {u'hits': {u'hits': [{u'_source': {u'certificate_common_name': u'sls.update.microsoft.com'}}]}}, Consists of a Dictionary, nested in a list, nested in a dictionary.'''

# Extract the results of the first dictionary to get the list of results 
    CN_NAME_LIST_1 = CN_NAME_SEARCH.get('hits', {}).get('hits')
   
# Iterate through the resulting list to extract the remaining values
    for CN_NAME_DIC_1 in CN_NAME_LIST_1:
        CN_NAME_DIC_2 = CN_NAME_DIC_1.get('_source', {}).get('certificate_common_name')

# Only want the top level domain from the results.  Spliting the string, select the last two fields then join them with a '.'
        CN_NAME_SPLIT = CN_NAME_DIC_2.split(".")[-2:]
        CN_NAME_1 = '.'.join(CN_NAME_SPLIT) 
	CN_NAME_2 = str(CN_NAME_1)
	CN_NAME = CN_NAME_2.lower()
	if ' ' in CN_NAME:
            CN_NAME = CN_NAME.split()[0]
        if CN_NAME not in CN_NAME_UNIQUE:
            CN_NAME_UNIQUE.append(CN_NAME)
# Send a query to elasticsearch bro_dns for a dns_request to the TLD of the SSL CN field.
# Add the wildcard to the beginning of the script.
            CN_NAME_WILDCARD = str(("*") + CN_NAME)

##############################################################################################################################################
# Search Elasticsearch bro_dns records for a query containing the Parent.TLD domain refenrenced in the CN field name of the SSL Certificate. #
##############################################################################################################################################
            DNS_PARENT_DOMAIN_SEARCH = es.search(index="*:logstash-*", body={"query": {"bool": {"must": [{"wildcard" : {"query.keyword": CN_NAME_WILDCARD}}], "filter": [{ "range": {"@timestamp": {"gte": "now-36h", "lte": "now"}}}]}}}, filter_path=['hits.hits._source.uid'], size=1)

# Change the list to a string and seach for the string uid.  Uid is only present in records that return a match
            DNS_PARENT_DOMAIN_SEARCH_STR = str(DNS_PARENT_DOMAIN_SEARCH.get('hits', {}).get('hits'))
            if 'uid' not in  DNS_PARENT_DOMAIN_SEARCH_STR:
                print("No DNS query found for", CN_NAME) 
##############################################################
# Search Elasticsearch to get the UID to pass to bro_notices #
##############################################################
                SSL_SEARCH = es.search(index="*:logstash-*", body={"query": {"bool": {"must": [{"wildcard" : {"certificate_common_name": CN_NAME_WILDCARD}}], "filter": [{ "term": {"event_type": "bro_ssl"}}]}}}, size=1)
                SSL_SEARCH_LIST_1 = SSL_SEARCH.get('hits', {}).get('hits')
            #Convert to a sting inorder to search for the word None.  Issue: Python cannot iterate over a null value (returned as "None"
                SSL_SEARCH_LIST_STR = str(SSL_SEARCH_LIST_1)
                if len(SSL_SEARCH_LIST_STR) >= 3:
                    SSL_SEARCH_LIST_SOURCE = SSL_SEARCH_LIST_1[0]
                    for SSL_SEARCH_DIC_1 in SSL_SEARCH_LIST_SOURCE:
                        SSL_UID = str(SSL_SEARCH_LIST_SOURCE.get('_source', {}).get('uid'))
                        if "None" in SSL_UID:
                            SSL_UID = CN_NAME
                        SSL_SRC_IP = str(SSL_SEARCH_LIST_SOURCE.get('_source', {}).get('source_ip'))
		        if "None" in SSL_SRC_IP:
                            SSL_SRC_IP = '127.0.0.1'
                        SSL_DEST_IP = str(SSL_SEARCH_LIST_SOURCE.get('_source', {}).get('destination_ip'))
                        if "None" in SSL_DEST_IP:
                            SSL_DEST_IP = '127.0.0.1'    
                        SSL_TIMESTAMP = str(SSL_SEARCH_LIST_SOURCE.get('_source', {}).get('timestamp'))
                        if "None" in SSL_TIMESTAMP:
                            SSL_TIMESTAMP = '2019-05-24T22:00:00.000Z'
                        SSL_COUNTRY_NAME = str(SSL_SEARCH_LIST_SOURCE.get('_source', {}).get('destination_geo', {}).get('country_name'))
                        if "None" in SSL_COUNTRY_NAME:
                            SSL_COUNTRY_NAME = 'UNKNOWN'

###############################
# Send results to Bro_notices #
###############################           
                    if "None" not in SSL_UID:
			print(SSL_SRC_IP)
			print(SSL_TIMESTAMP)		     
                        BRO_NOTICE = es.index(index='logstash-bro-2019.05.21', doc_type='doc', body={"source_port": 443, "port": 443, "host": "-", "syslog-sourceip": "127.0.0.1", "protocol": "tcp", "sub_msg": CN_NAME, "peer_description": "-", "event_type": "bro_notice", "syslog-tags": ".source.s_bro_notice", "uid": SSL_UID, "p": 443, "syslog-facility": "-", "logstash_time": 0.0, "destination_ip": SSL_DEST_IP, "destination_ips": SSL_DEST_IP, "syslog-host": "-", "note": "SSL::No_DNS_Query_for_Cert_CN", "@timestamp": SSL_TIMESTAMP, "dropped": "false", "message": "-}", "timestamp": SSL_TIMESTAMP, "tags": ["syslogng", "bro", "internal_destination", "internal_source"], "msg": "Common Name Field has no DNS query for the parent domain.", "ips": ["-","-"], "destination_port": 443, "source_ips": SSL_SRC_IP, "action": ["Notice::ACTION_LOG"], "@version": "1", "source_ip": SSL_SRC_IP, "syslog-file_name": "cn_analysis.py", "syslog-host_from": "-", "suppress_for": 3600, "syslog-priority": "notice", 'destination_geo': {'country_name': SSL_COUNTRY_NAME}})