"""
The idea of this program if to mimic the functionality of `javaws`, i.e.
fetching of a '.jlnp' file from a webserver, parsing it, retrieving required
'.jar' files and constructing a suitable commandline for a JRE.
"""

# SPDX-License-Identifier: GPL-2.0-or-later

import os
import signal
import subprocess
import sys
import shutil
import tempfile

from bs4 import BeautifulSoup
import requests

# Hints:
# run `wmname LG3D`

# The following env variables might be helpful
# JDK_JAVA_OPTIONS='-Dsun.java2d.opengl=true'
# AWT_TOOLKIT=MToolkit
# _JAVA_OPTIONS=-Dawt.useSystemAAFontSettings=lcd"

def signal_handler(signum, frame):
    del frame
    signame = signal.Signals(signum).name
    print()
    print(f'Signal handler called with signal {signal.strsignal(signum)} / {signame}({signum})')
    if signum in [signal.SIGINT]:
        print("Calling cleanup()", file=sys.stderr)
        cleanup()
    sys.exit(1)


def download_file(dest_dir, d_url):
    d_file_name = d_url.split('/')[-1]
    d_r = requests.get(url, timeout=10)
    with open(os.path.join(dest_dir, d_file_name), 'wb') as f:
        for chunk in d_r.iter_content(chunk_size=512 * 1024):
            if chunk:
                f.write(chunk)

def cleanup():
    shutil.rmtree(d)

args = ""
d = ""

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if len(sys.argv) != 2:
    print(f"{sys.argv[0]} takes exactly one argument, the URL to a .jlnp file.", file=sys.stderr)
    print(f"Number of arguments that were provided: {len(sys.argv) - 1}.", file=sys.stderr)
    if len(sys.argv) > 1:
        print("Arguments:", file=sys.stderr)
        for i, arg in enumerate(sys.argv[1:]):
            print(f" {i}: '{sys.argv[i]}'.", file=sys.stderr)
    sys.exit(1)

r = requests.get(sys.argv[1], timeout=10)
if r.status_code != 200:
    print(f"Unexpected http return code {r.status_code}. Exiting.", file=sys.stderr)
    sys.exit(1)

MIME_TYPE = "application/x-java-jnlp-file"
if r.headers['content-type'] != MIME_TYPE:
    print(f"Warning: http response content type was expected to be {MIME_TYPE} but is {r.headers['content-type']}", file=sys.stderr)

d = tempfile.mkdtemp()

soup = BeautifulSoup(r.text, 'xml')
app_desc_main = soup.find("application-desc")["main-class"]
app_desc_arg = soup.find("application-desc").argument.string

soup_jars = soup.resources.find_all("jar")

unpack200_bin = os.environ["UNPACK200_BIN"] if "UNPACK200_BIN" in os.environ else "unpack200"
java = os.environ["JAVA_BIN"] if "JAVA_BIN" in os.environ else "java"

for jar in soup_jars:
    file_name = jar["href"].strip()
    pack_file_name = file_name + ".pack.gz"
    url = f'http://{app_desc_arg}/{pack_file_name}'
    download_file(d, url)
    try:
        subprocess.run([
            unpack200_bin,
            os.path.join(d, pack_file_name),
            os.path.join(d, file_name),
            ], check=True)
    except FileNotFoundError:
        print("If you don't have `unpack200` in your PATH, set the environment variable 'UNPACK200_PATH'", file=sys.stderr)
        cleanup()
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(e)
        cleanup()
        sys.exit(1)

jars = ":".join([os.path.join(d, _["href"].strip()) for _ in soup_jars])
args = " ".join(filter(None, [args, f" \\\n\t-cp {jars}"]))

for property_ in soup.resources.find_all("property"):
    args += f" \\\n\t-D{property_['name']}={property_['value']}"

app = " ".join([java, args, app_desc_main, app_desc_arg])
print(f"I'll be running:\n{app}")
try:
    subprocess.run(app, shell=True, check=True)
except subprocess.CalledProcessError as e:
    print(e)
    cleanup()
    sys.exit(1)
cleanup()
