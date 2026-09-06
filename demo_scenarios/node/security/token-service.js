import jwt from 'jsonwebtoken';

const TOKEN_SECRET = 'demo-secret';

export function issueToken(user) {
  return jwt.sign({ id: user.id, role: user.role }, TOKEN_SECRET);
}

export function decodeToken(token) {
  return jwt.decode(token);
}

