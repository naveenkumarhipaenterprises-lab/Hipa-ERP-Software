import SpiceArt from '../../../components/common/SpiceArt'

/** Decorative brand panel (no data). */
export default function BrandBanner() {
  return (
    <section className="brand-banner" aria-label="HIPA MASALA">
      <div className="brand-banner__text">
        <h2>Pure Spices. A Better Tomorrow.</h2>
        <p>From nature to your kitchen, with quality in every step.</p>
      </div>
      <SpiceArt className="brand-banner__art" width={220} />
    </section>
  )
}
