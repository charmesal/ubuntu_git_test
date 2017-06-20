#!/usr/bin/python3

from __future__ import absolute_import, print_function, unicode_literals

import os
import os.path
import sys
import re
import datetime

from apport.hookutils import *

from apport import unicode_gettext as _

pci_devices = [
    { 'name':'i810',        're':'(8086:7121)',        'supported':False },
    { 'name':'i810dc',      're':'(8086:7123)',        'supported':False },
    { 'name':'i810e',       're':'(8086:7125)',        'supported':False },
    { 'name':'i815',        're':'(8086:1132|82815)',  'supported':False },
    { 'name':'i830',        're':'(8086:3577|82830)',  'supported':False },
    { 'name':'i845',        're':'(8086:2562|82845G)', 'supported':False },
    { 'name':'i855',        're':'(8086:3582|855GM)',  'supported':False },
    { 'name':'i865',        're':'(8086:2572|82865G)', 'supported':False },
    { 'name':'i915g',       're':'(8086:2582)'       },
    { 'name':'i915gm',      're':'(8086:2592|915GM)' },
    { 'name':'e7221',       're':'(8086:258a)',        'supported':False },
    { 'name':'i945g',       're':'(8086:2772|945G[ \/]|82945G[ \/])' },
    { 'name':'i945gm',      're':'(8086:27a2|945GM[ \/]|82945GM[ \/])' },
    { 'name':'i945gme',     're':'(8086:27ae|945GME|82945GME)' },
    { 'name':'IGDg',        're':'(8086:a001)' },
    { 'name':'IGDgm',       're':'(8086:a011)' },
    { 'name':'pineviewg',   're':'(8086:a001)' },
    { 'name':'pineviewgm',  're':'(8086:a011)' },
    { 'name':'i946gz',      're':'(8086:2972|82946GZ)' },
    { 'name':'g35',         're':'(8086:2982|82G35)' },
    { 'name':'i965q',       're':'(8086:2992|Q965)' },
    { 'name':'i965g',       're':'(8086:29a2|G965)' },
    { 'name':'g33',         're':'(8086:29c2|82G33)' },
    { 'name':'q35',         're':'(8086:29b2)' },
    { 'name':'q33',         're':'(8086:29d2)' },
    { 'name':'i965gm',      're':'(8086:2a02|GM965)' },
    { 'name':'i965gme',     're':'(8086:2a12)' },
    { 'name':'gm45',        're':'(8086:2a42)' },
    { 'name':'IGDeg',       're':'(8086:2e02)' },
    { 'name':'q45',         're':'(8086:2e12)' },
    { 'name':'g45',         're':'(8086:2e22)' },
    { 'name':'g41',         're':'(8086:2e32)' },
    { 'name':'b43',         're':'(8086:2e42)' },
    { 'name':'clarkdale',   're':'(8086:0042)' },
    { 'name':'arrandale',   're':'(8086:0046)' },
    { 'name':'sandybridge-gt1',   're':'(8086:0102)' },
    { 'name':'sandybridge-m-gt1', 're':'(8086:0106)' },
    { 'name':'sandybridge-s',     're':'(8086:010a)' },
    { 'name':'sandybridge-gt2',   're':'(8086:0112)' },
    { 'name':'sandybridge-m-gt2', 're':'(8086:0116)' },
    { 'name':'sandybridge-gt2+',  're':'(8086:0122)' },
    { 'name':'sandybridge-m-gt2+','re':'(8086:0126)' },
    ]
for device in pci_devices:
    device['rc'] = re.compile(device['re'], re.IGNORECASE)

def get_pci_device(text):
    regex_vga = re.compile('VGA compatible controller (.*)', re.IGNORECASE)

    lines = regex_vga.findall(text)
    if len(lines) > 0:
        for l in lines:
            if len(l.strip())>0:
                for device in pci_devices:
                    if device['rc'].search(l.strip()):
                        return device
    return None

def get_signature(text):
    '''Assumes the format of the i915_error_state file'''
    codes = {
        'EIR' :      re.compile("EIR: 0x([0-9a-fA-F]+)"),
        'ESR' :      re.compile("ESR: 0x([0-9a-fA-F]+)"),
        'PGTBL_ER' : re.compile("PGTBL_ER: 0x([0-9a-fA-F]+)"),
        'IPEHR' :    re.compile("IPEHR: 0x([0-9a-fA-F]+)"),
        }
    section = None
    signature = ''

    for line in text.split("\n"):
        if line == 'Blitter command stream:':
            section = 'blitter'
        elif line == 'Video (BSD) command stream:':
            section = 'video'
        elif line == 'Render command stream:':
            section = 'render'
        elif line[:8] == 'Active [':
            section = 'active'
            return signature
        else:
            for k, r in codes.items():
                match = r.search(line)
                if match and match.group(1) != "00000000":
                    if section:
                        signature += " %s.%s: 0x%s" %(section, k, match.group(1))
                    else:
                        signature += " %s: 0x%s" %(k, match.group(1))

    return signature

def main(argv=None):
    if argv is None:
        argv = sys.argv

    if '--force' not in argv:
        # If not a development release, bail
        rel = command_output(['lsb_release', '-d'])
        if 'development branch' not in rel:
            return 1

        from apport.packaging_impl import impl as packaging
        if not packaging.enabled():
            return 2

    import apport.report
    report = apport.report.Report(type='Crash')
    report.setdefault('Tags', '')
    report.setdefault('Title', 'GPU lockup')

    report.add_os_info()
    report.add_proc_info()
    report.add_user_info()

    package = 'xserver-xorg-video-intel'
    try:
        package_version = apport.packaging.get_version(package)
    except ValueError as e:
        if 'does not exist' in e.message:
            package_version = 'unknown'
    report['Package'] = '%s %s' % (package, package_version)
    report['Tags'] += ' freeze'
    report['Lspci'] = command_output(['lspci', '-vvnn'])
    device = get_pci_device(report['Lspci'])
    if device and 'name' in device:
        if '--force' not in argv:
            if 'supported' in device and device['supported'] == False:
                # Unsupported chipset; we don't want bugs reported for this HW
                return 3
        report['Chipset'] = device['name']
        report['Title'] = "[%s] GPU lockup" %(device['name'])

    try:
        attach_hardware(report)
        attach_related_packages(report, ["xserver-xorg", "libdrm2", "xserver-xorg-video-intel"])
    except:
        # attach_hardware can fail with UnicodeDecodeError parsing DMI (See LP: #1062042)
        # attach_related_packages can fail with SystemError if apt isn't updated (See LP: #1103061)
        pass
    attach_file_if_exists(report, '/etc/X11/xorg.conf', 'XorgConf')
    attach_file(report, '/var/log/Xorg.0.log', 'XorgLog')
    attach_file_if_exists(report, '/var/log/Xorg.0.log.old', 'XorgLogOld')
    attach_file_if_exists(report, '/sys/kernel/debug/dri/0/i915_error_state', 'i915_error_state')

    signature = get_signature(report.get('i915_error_state', ''))
    if not signature:
        # Lack of a signature generally indicates an invalid error state, such
        # as a false positive or a '0x000000' (non-)error state.  In either case,
        # the bug won't be upstreamable nor otherwise actionable.
        if '--force' not in argv:
            return 4

    report['Title'] += " " + signature
    report['DuplicateSignature'] = "%s %s" %(report['Title'], report['DistroRelease'])

    nowtime = datetime.datetime.now()
    report_filename = '/var/crash/%s.%s.crash' % (package, str(nowtime).replace(' ', '_'))

    if '--stdout' in argv:
        print("# %s" %(report_filename))
        report.write(sys.stdout.buffer)
        return 0

    report_file = os.fdopen(os.open(report_filename, os.O_WRONLY|os.O_CREAT|os.O_EXCL), 'wb')
    os.chmod(report_filename, 0o600)

    try:
        report.write(report_file)
    finally:
        report_file.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())