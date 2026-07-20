export default function HomePage() {
  return (
    <main style={{
      minHeight: '100vh',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      fontFamily: 'system-ui, sans-serif',
      padding: '2rem',
      backgroundColor: '#f8fafc',
    }}>
      <div style={{ maxWidth: 720, textAlign: 'center' }}>
        <h1 style={{ marginBottom: '1rem', fontSize: '2.5rem' }}>Привет, Next.js!</h1>
        <p style={{ fontSize: '1.125rem', lineHeight: 1.75 }}>
          Это базовый проект Next.js. Запусти <code>npm install</code>, затем <code>npm run dev</code>.
        </p>
      </div>
    </main>
  );
}
