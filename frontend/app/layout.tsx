import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title:'Coronary Atlas | Patient assessment', description:'Explore patient-level coronary predictions with interactive BodyParts3D anatomy.' };
export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}
