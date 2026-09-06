export async function pay(body) {
  return fetch('/api/checkout', { method: 'POST', body: JSON.stringify(body) });
}

