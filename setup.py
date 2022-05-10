from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in pivottech_alramat/__init__.py
from pivottech_alramat import __version__ as version

setup(
	name='pivottech_alramat',
	version=version,
	description='customization and development on erpnext for alramat company',
	author='Pivottech',
	author_email='sys.pivoterp@gmail.com',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
