import adapter from '@sveltejs/adapter-static';

const config = {
  kit: {
    adapter: adapter({
      fallback: '200.html',
      precompress: true,
    }),
  },
};

export default config;
