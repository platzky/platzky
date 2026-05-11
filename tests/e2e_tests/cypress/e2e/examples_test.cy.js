describe('Example plugins', () => {
  it('red_letter: [red] shortcode wraps content in a red span', () => {
    cy.visit('/blog/red-test')
    cy.get('span[style="color:red"]').contains('danger')
  })

  it('red_letter: letter "a" is wrapped in a red span', () => {
    cy.visit('/blog/red-test')
    cy.get('span[style="color:red"]').contains('a')
  })
})
