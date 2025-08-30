from setuptools import setup, find_packages

setup(
    name='tb-web-backend',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'requests',
        'numpy',
    ],
    author='Ryan Nguyen',
    author_email='ryannguyenc@gmail.com',
    description='A backend FastAPI server for running terminal-bench in the web',
    long_description=open('../README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
