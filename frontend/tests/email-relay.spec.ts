import {expect, test} from '@playwright/test';

test('verification relay rejects requests without its server secret', async ({request}) => {
  const response = await request.post('/api/internal/send-verification', {
    data: {recipient: 'someone@example.com', token: 'one-time-token'},
  });
  expect(response.status()).toBe(401);
});
