import { SignJWT, jwtVerify } from 'jose';

export async function sign(payload: Record<string, unknown>, secret: string, expiry: string = '7d'): Promise<string> {
const secretKey = new TextEncoder().encode(secret);
return new SignJWT(payload)
.setProtectedHeader({ alg: 'HS256' })
.setIssuedAt()
.setExpirationTime(expiry)
.sign(secretKey);
}

export async function verify(token: string, secret: string): Promise<Record<string, unknown>> {
const secretKey = new TextEncoder().encode(secret);
const { payload } = await jwtVerify(token, secretKey);
return payload as Record<string, unknown>;
}