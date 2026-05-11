describe('Admin authentication', () => {
  it('redirects back to the originally requested page after login', () => {
    cy.visit('/admin/help')

    // Should be on the login page (not yet on help)
    cy.contains('Login')

    // Log in as admin via fake login
    cy.get('form[action*="fake-login/admin"]').submit()

    // Should land on /admin/help, not /admin/
    cy.url().should('include', '/admin/help')
    cy.contains('Shortcodes')
  })
})
