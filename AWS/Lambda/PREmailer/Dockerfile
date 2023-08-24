FROM amazonlinux:2

RUN yum install -y pip python3-devel zip

RUN amazon-linux-extras enable python3.8

RUN yum install -y python38

ADD pr_emailer.py package.sh requirements.txt .

RUN bash package.sh

RUN mkdir package/

RUN mv function.zip package/
