FROM node:alpine

WORKDIR /app

RUN apk add chromium

ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD true
ENV PUPPETEER_EXECUTABLE_PATH /usr/bin/chromium-browser
ENV ENV docker

COPY . .

RUN npm config set registry https://registry.npm.taobao.org
RUN npm install

CMD [ "node", "verify.js" ]
# should run with {args: ['--no-sandbox', '--disable-gpu']}