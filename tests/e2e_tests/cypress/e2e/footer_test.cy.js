describe('Footer', () => {
  it('shows the site-wide footer in the current language', () => {
    cy.visit('/blog/')
    cy.get('#footer-row').should('contain.text', 'English footer')
    cy.get('#footer-row a[href="/blog/"]').should('exist')

    cy.get('#languages-menu').click()
    cy.contains('.dropdown-item', 'polski').click()

    cy.get('#footer-row').should('contain.text', 'Polska stopka')
  })

  it('lets a page replace the site-wide footer', () => {
    cy.visit('/blog/page/strona')
    cy.get('#footer-row').should('contain.text', 'Stopka strony')
    cy.get('#footer-row').should('not.contain.text', 'English footer')
  })
})
