# VDR Streamdev & XMLTV Proxy

Initially developed as a converter to be able to use VDR EPG as XMLTV source and VDR streamdev-server plugin streams as LiveTV source in Jellyfin it is now a standalone server not only being used with Jellyfin. You decide where to run the proxy. It only needs access to VDR and must be accessible from a streaming-client of your choice, e.g. Jellyfin or VLC. VDR stream can be both used with direct connection to VDR (channels.m3u will get the VDR ip) or in proxy mode (channels.m3u will get the proxy ip) to completely hide VDR from streaming client.

## Features

- **Online VDR EPG to XMLTV conversion** On the fly conversion of epg.data to XMLTV structure perfectly usable in e.g. Jellyfin's Live-TV EPG provider
- **Playlist creation from VDR channels** Providing a m3u file to use in e.g. Jellyfin's Live-TV m3u tuner or directly with e.g. VLC.
- **Reverse proxy for streamdev-server streams** Providing a reverse proxy functionality to hide your VDR instance behind.

## Quickstart Deployment

1. Unpack the compressed project files.
2. Execute the self-checking interactive bash script:

   ```bash
   chmod +x install.sh
   sudo ./install.sh --install
   ```

3. Update parameters according to your specific environment (see Configuration) within your new default configuration layout directory at `/etc/vdr_proxy/config.ini` and restart jellyfin-vdr-proxy.

## Quickstart to use Jellyfin as streaming client with XMLTV spport:
1. Add http://PROXYADDRESS/channels.m3u as Jellyfin Live-TV tuner (m3u tuner)
2. Add http://PROXYADDRESS/epg.xml as Jellyfin Live.TV EPG provider (xmltv)

## Restless Uninstallation

To clear the suite and revert system elements safely, execute:

```bash
sudo ./install.sh --uninstall
```

## Configuration

### Section [VDR]

| Parameter | Value |
| :--- | :--- |
| protocol | "http" or "https", depending on your VDR setup. Default "http" |
| ip | **Mandatory** IP of VDR to use as streaming server and EPG source. Must be accessible from proxy and in cae of direct link also from streaming client. |  

### Section [EPG]

| Parameter | Value |
| :--- | :--- |
| mode | "file" (to use epg.data) or "svdrp" (to directly use VDR LSTE command). Default svdrp |
| epgfile | Path to "epg.data" if "epg_mode=file". Default "/var/lib/vdr/epg.data" |

### Section [SVDRP]

| Parameter | Value |
| :--- | :--- |
| port | SVDRP Port if "epg_mode=svdrp". Default "6419" |
| timeout | Timeout for SVDRP connection if "epg_mode=svdrp". Default "30" |

### Section [STREAMDEV]

| Parameter | Value |
| :--- | :--- |
| chunk_size | Chunk size of stream. Default 65536 |
| port | streamdev-server port. Default "3000" |
| protocol | "http" or "https". Defalt "http" |
| streamtype | EIther TS, ES, PES or EXT. Default "TS" |

### Section [PROXY]

| Parameter | Value |
| :--- | :--- |
| server_ip | Proxy listen IP. Default "0.0.0.0" |
| client_ip | IP to connect to in case of proxy VDR stream. Default first IP of local machine. |
| protocol | http or https. Default "http" |
| port | Proxy listen port. Default "8080" |
| streamproxy | "True" to proxy original VDR stream via proxy ip. "False" to direct connect to VDR stream via VDR ip. Default "True" |
| ssl_cert_file | Path to SSL certificate file. For https only - UNTESTED |
| ssl_key_file | Path to SSL key file. For https only - UNTESTED |

### Section [TRANSCODE]

| Parameter | Value |
| :--- | :--- |
| vbitrate | Video bitrate. Default source video |
| vsize | Video size. Default source video |
| vcodec | Video codec. Default hevc_qsv |
| abitrate | Audio bitrate. Default source audio |
| acodec | Audio codec. Defaul source audio |

#### Video Codecs

| Hardware / Hersteller | Schnittstelle | H.264 Codec | H.265 (HEVC) Codec | AV1 Codec |
| :--- | :--- | :--- | :--- | :--- |
| Intel (CPU / Arc) | QSV | h264_qsv | hevc_qsv | av1_qsv |
| NVIDIA (alle OS) | NVENC | h264_nvenc | hevc_nvenc | av1_nvenc |
| AMD (Windows) | AMF | h264_amf | hevc_amf | av1_amf |
| AMD (Linux) | VA-API | h264_vaapi | hevc_vaapi | av1_vaapi |

### Section [AUTHENTICATION]

| Parameter | Value |
| :--- | :--- |
| enabled | Enable/disable authentication. Default "False" |
| username | Username |
| password | Password |