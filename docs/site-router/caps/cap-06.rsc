# svr-cap-06 - runs automatically after reset via run-after-reset=
/system identity set name=svr-cap-06
/interface bridge add name=bridgeLocal
/interface bridge port add bridge=bridgeLocal interface=ether1
/interface bridge port add bridge=bridgeLocal interface=ether2
/ip dhcp-client add interface=bridgeLocal disabled=no
/interface wireless cap set enabled=yes bridge=bridgeLocal interfaces=wlan1,wlan2 discovery-interfaces=bridgeLocal
/system clock set time-zone-name=Europe/Moscow
/ip service set telnet disabled=yes
/ip service set ftp disabled=yes
/ip service set www disabled=yes
:log warning "svr-cap-06 configured after reset"
