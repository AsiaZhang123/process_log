from setuptools import setup, find_packages

with open("README.md", "r") as fh:
  long_description = fh.read()

setup(
    name="logging_process",
    packages=find_packages(),
    version='0.9.4',
    description="多进程日志，继承自python官方logging，解决多进程下log日志丢失及混乱问题",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="zyz",
    author_email='329737612@qq.com',
    url="https://github.com/AsiaZhang123/process_log",
    download_url='https://github.com/AsiaZhang123/process_log/issues',
    classifiers=[
        "Programming Language :: Python",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'portalocker>=2.3.0'
    ],
)