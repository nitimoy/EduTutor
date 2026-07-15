import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PUBLIC = ['/', '/auth'];

export function proxy(request: NextRequest) {
    const { pathname } = request.nextUrl;

    if (PUBLIC.includes(pathname) || pathname.startsWith('/_next') || pathname.startsWith('/api') || pathname.includes('.')) {
        return NextResponse.next();
    }

    if (!request.cookies.get('edu_logged_in')) {
        return NextResponse.redirect(new URL('/auth', request.url));
    }

    return NextResponse.next();
}

export const config = {
    matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
