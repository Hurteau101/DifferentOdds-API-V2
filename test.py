import requests
import json

url = "https://betway.com/g/services/api/events/v2/GetCategoryDetails"

payload = json.dumps({
  "BrandId": 3,
  "LanguageId": 25,
  "TerritoryId": 38,
  "TerritoryCode": "CA",
  "ClientTypeId": 2,
  "JurisdictionId": 2,
  "ClientIntegratorId": 1,
  "CorrelationId": "93d39040-7ddf-499f-b327-c783e13cdc45",
  "CategoryCName": "basketball"
})
headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0',
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'en-US,en;q=0.9',
  'Accept-Encoding': 'gzip, deflate, br, zstd',
  'Content-Type': 'application/json',
  # 'x-correlation-id': '93d39040-7ddf-499f-b327-c783e13cdc45',
  # 'traceparent': '00-3c762f5adb304d02912f1c193eb298ff-90ef03a82137437c-01',
  'Origin': 'https://betway.com',
  'Connection': 'keep-alive',
  # 'Referer': 'https://betway.com/g/en-ca/sports/cat/basketball/all',
  # 'Cookie': 'opennext=true; visitId=1c6126a3-2792-4366-83a2-7170d602e5e9; bw_SessionId=1c6126a3-2792-4366-83a2-7170d602e5e9; SpinSportVisitId=1c6126a3-2792-4366-83a2-7170d602e5e9; clientId=48a26aed-937b-4993-a931-550ffbf27ab6; bw_BrowserId=48a26aed-937b-4993-a931-550ffbf27ab6; deviceId=uLYxZNgOZSPQc80mR8GDO; __cf_bm=mTglIO6Ir3RrAbQ.amSl6qvWxlzPg42dbGpLbZTuEQo-1772515988-1.0.1.1-SVZtWCVroYiosErIJNh.vLlBuQAPxpGgg7lDvOEwg5y2rLA9DzhFUgXe0jqBeYtx_fPGOHOQ3.t2aHxsA_Ebe4cKHifUKwNURROdbNrcOS0; userLanguage=en-ca; ssc_subbrand=sports; btag1=749cb431-1784-4a65-bb64-7605d68089b6; TrackingVisitId=749cb431-1784-4a65-bb64-7605d68089b6; OptanonConsent=isGpcEnabled=0&datestamp=Mon+Mar+02+2026+23%3A03%3A13+GMT-0600+(Central+Standard+Time)&version=202505.2.0&browserGpcFlag=0&isIABGlobal=false&hosts=&consentId=50c55c1d-7077-42c0-82ac-d98030b22a56&interactionCount=1&isAnonUser=1&landingPath=NotLandingPage&groups=C0004%3A1%2CC0001%3A1%2CC0002%3A1%2CC0003%3A1&intType=1; fs_lua=1.1772516234873; fs_uid=^#o-8KGQ-eu1^#86223fa7-538a-4a9e-95da-1f0482171e8f:cc893b55-3746-4c23-b338-8f57a63f90ed:1772514186885::1^#/1804050188; _gcl_au=1.1.2024231689.1772514191; _sp_id.0d73=b37910fb-0b5f-4500-ac1f-46cf7d6b1bdd.1772514191.2.1772516477.1772514191.7c96a79a-9ca0-4815-9b74-02e5f4f43132.df7fed53-1c69-4ddc-8929-3099a50687ee.b77a5f77-afe6-44e0-80c2-431f004fa27b.1772516162045.5; _ga_HH1EZEXGZB=GS2.1.s1772516162^$o2^$g1^$t1772516477^$j60^$l0^$h155693298^$dhnBb-lY-pTUdYl9EY3MiH8z1_KAHrl2rwA; _ga=GA1.1.1420585220.1772514191; _cq_duid=1.1772514191.ck6l8r1i9hqc7F84; _cq_suid=1.1772514191.XgbsEoQIBqUfYsXH; _scid=_44epNU2Uc-Ah2IYPa5j6wOT2iiUiM18; _scid_r=_44epNU2Uc-Ah2IYPa5j6wOT2iiUiM18; _rdt_uuid=1772514191709.690c749c-880e-415d-8eba-43738f1d83a1; __qca=P1-8c5d7f9a-70a1-40b4-bce1-1021aa9e75fe; _fbp=fb.1.1772514192275.80030421237861898; _sctr=1%7C1772431200000; OptanonAlertBoxClosed=2026-03-03T05:03:13.948Z; _sp_ses.0d73=*; lastUserLogin=sports; __cf_bm=uBrBpIll6VcqfPViedmPeIcbR4BhaTzyMCuDAg0Y3vY-1772560653-1.0.1.1-gRXeCt6sO6k2K34sFgyvTv1JbVwU49CJ5ZCH.DZ5PYVZNzk6ExP1n6dVSkW3hKLWGQVxkXR.4jRIcx_OpgRYOt7n_sr9.qlaw0qyJ.tQUbY',
  'Sec-Fetch-Dest': 'empty',
  'Sec-Fetch-Mode': 'cors',
  'Sec-Fetch-Site': 'same-origin',
  'Priority': 'u=0',
  'TE': 'trailers'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)
