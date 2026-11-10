import { useState } from 'react'
import { branding } from '../branding'
import { NavLink } from 'react-router-dom'
import { useUser } from '../context/UserContext'

export default function Header() {
  const { me } = useUser()
  const [logoFailed, setLogoFailed] = useState(false)
  return (
    <header className="app-header">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <NavLink to="/" className="brand-home" aria-label={`${branding.appName} home`}>
        {branding.logoPath && !logoFailed && (
          <img className="logo" src={branding.logoPath} alt="" onError={() => setLogoFailed(true)} />
        )}
        <span className="brand-copy">
          {branding.organizationName && <span className="brand-organization">{branding.organizationName}</span>}
          <span className="app-title">{branding.appName}</span>
        </span>
      </NavLink>
      <nav aria-label="Primary">
        <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>
          Integrations
        </NavLink>
        <NavLink to="/dag" className={({ isActive }) => (isActive ? 'active' : '')}>
          DAG
        </NavLink>
      </nav>
      <span className="spacer" />
      {me && (
        <div className="user-chip">
          <span className="user-name">{me.user.display_name || me.user.email}</span>
          <span className={`user-role ${me.is_admin ? 'admin' : ''}`}>
            {me.is_admin ? 'Integration team' : 'General user'}
          </span>
        </div>
      )}
    </header>
  )
}
