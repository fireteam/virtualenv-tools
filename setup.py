import os
from setuptools import setup

readme = open(os.path.join(os.path.dirname(__file__), 'README'), 'r').read()

setup(
    name='virtualenv-tools',
    author='Fireteam Ltd.',
    author_email='support@fireteam.net',
    version='1.0',
    url='http://github.com/fireteam/virtualenv-tools',
    py_modules=['virtualenv_tools'],
    description='A set of tools for virtualenv',
    long_description=readme,
    entry_points={
        'console_scripts': [
            'virtualenv-tools = virtualenv_tools:main'
        ]
    },
    zip_safe=False,
    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python'
    ]
)
