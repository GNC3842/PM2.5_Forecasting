## OpenAQ

**Request with curl:** 
```
curl --request GET \
--url "https://api.openaq.org/v3/locations/ID" \
--header "X-API-Key: YOUR-OPENAQ-API-KEY"
```

**Rate limits:** 60/minutes and 2000/hours 
Carefull: Exceeding API rate limits repeatedly can lead to either a temporary or permanent ban from the OpenAQ API. To maintain uninterrupted access, plan your API requests carefully.

**Datetime format:** ```YYY-MM-DDTHH:MM:SS.SSSSZ```

**OpenAQ SDK Pyhton:** ```pip install openaq``` and use with
```
from openaq import OpenAQ

client = OpenAQ(api_key="replace-with-valid-openaq-api-key")

location = client.locations.get(2178)

client.close()

print(location.results[0].name)
```

Check: *https://python.openaq.org/getting-started/quick-start/*