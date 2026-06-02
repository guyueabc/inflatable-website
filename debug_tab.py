with open("D:\\2\\inflatable-website\\templates\\admin.html", "r", encoding="utf-8") as f:
    html = f.read()

ts = html.find('id="tabTraffic"')
te = html.find("</div>", html.find("traffic-container"))
print("Traffic tab section:")
print(html[ts:ts+2000])
