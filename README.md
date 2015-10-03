# ADP Paycheck Downloader

## TL;DR

Python script to download paychecks

```
adp.py username [password]
```

ADP's website has some JSP craziness that only allows you to view one paycheck
at a time. Additionally, their notification emails don't actually send you the
paycheck, but rather just link to the site.

This python script will download all your paychecks to folders in the current
directory, one folder for each year, skipping the files that are already
downloaded.

It is a total hack and may stop working, but you may also find it useful.
