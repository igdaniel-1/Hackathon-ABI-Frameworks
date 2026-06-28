const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  app.use(
    ['/pcc', '/health'],
    createProxyMiddleware({
      target: 'https://hackathon.prod.pulsefoundry.ai',
      changeOrigin: true,
    })
  );
};
