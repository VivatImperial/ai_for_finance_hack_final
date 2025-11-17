import { defineConfig } from 'orval';

export default defineConfig({
  api: {
    input: './backend-openapi.json',
    output: {
      mode: 'split',
      target: './server/generated.ts',
      schemas: './types/api.ts',
      client: 'react-query',
      httpClient: 'fetch',
      override: {
        mutator: {
          path: './server/libs/fetch.ts',
          name: 'customFetch',
        },
        query: {
          useQuery: true,
          useMutation: true,
        },
      },
    },
  },
});

