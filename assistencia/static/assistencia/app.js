// Configura as confirmações e a indicação de salvamento em cada formulário da página.
document.querySelectorAll('form').forEach(form => {
  // Confirma operações relevantes e bloqueia novos envios enquanto a requisição está em andamento.
  form.addEventListener('submit', event => {
    let question = form.dataset.confirm;
    if (form.hasAttribute('data-status-confirm')) {
      const status = form.querySelector('[name=status]').value;
      if (status === 'cancelado') question = 'Cancelar esta OS? Confirme que informou o motivo e a destinação do equipamento.';
      if (status === 'finalizado') question = 'Finalizar o atendimento e confirmar a entrega do equipamento?';
    }
    if (question && !window.confirm(question)) { event.preventDefault(); return; }
    if (event.defaultPrevented) return;
    // Desativa cada botão de envio e informa visualmente que os dados estão sendo salvos.
    form.querySelectorAll('button[type=submit], button:not([type])').forEach(button => {
      button.disabled = true;
      button.textContent = 'Salvando…';
    });
    form.setAttribute('aria-busy', 'true');
  });
});
const wizard = document.querySelector('[data-wizard]');
const category = document.querySelector('[name=categoria]');
if (category) {
  // Adapta o rótulo de identificação: IMEI para celular e número de série para os demais equipamentos.
  const updateLabel = () => {
    const label = document.querySelector('label[for=id_identificacao]');
    if (label) label.textContent = category.value === 'celular' ? 'IMEI (opcional)' : 'Número de série (opcional)';
  };
  category.addEventListener('change', updateLabel);
  updateLabel();
}
if (wizard) {
  const steps = [...wizard.querySelectorAll('[data-step]')];
  const previous = wizard.querySelector('[data-prev]');
  const next = wizard.querySelector('[data-next]');
  const send = wizard.querySelector('[data-send]');
  // Localiza a primeira etapa com erro retornado pelo servidor para reapresentar seus campos.
  let current = Math.max(0, steps.findIndex(step => step.querySelector('.errorlist')));
  // Atualiza etapa visível, progresso acessível, botões de navegação e resumo dos dados preenchidos.
  const render = () => {
    // Mantém visíveis somente os campos da etapa atual.
    steps.forEach((step, i) => { step.hidden = i !== current; });
    // Destaca a etapa atual e a identifica para tecnologias assistivas.
    wizard.querySelectorAll('.wizard-progress li').forEach((li, i) => {
      li.classList.toggle('active', i === current);
      if (i === current) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
    });
    previous.hidden = current === 0;
    next.hidden = current === steps.length - 1;
    send.hidden = !next.hidden;
    const summary = wizard.querySelector('[data-summary]');
    // Consulta o valor de um campo pelo nome para montar o resumo sem inserir HTML do usuário.
    const value = name => wizard.elements[name].value;
    summary.textContent = `Confira seus dados\n${value('nome')} · ${value('telefone')}\n${value('email')}\n${value('categoria')} · ${value('marca') || 'Marca não informada'} · ${value('modelo') || 'Modelo não informado'}`;
  };
  // Valida a etapa atual antes de avançar e transfere o foco para o próximo grupo de campos.
  next.addEventListener('click', () => {
    // Encontra o primeiro campo que não atende à validação nativa do navegador.
    const invalid = [...steps[current].querySelectorAll('input,select,textarea')].find(input => !input.checkValidity());
    if (invalid) { invalid.reportValidity(); return; }
    current++; render(); steps[current].querySelector('input,select,textarea')?.focus();
  });
  // Volta uma etapa mantendo os dados e posicionando o foco para navegação por teclado.
  previous.addEventListener('click', () => { current--; render(); steps[current].querySelector('input,select,textarea')?.focus(); });
  // Reabre a etapa de um campo inválido caso o navegador detecte erro durante o envio.
  wizard.addEventListener('invalid', event => {
    // Identifica em qual etapa está o campo que originou o erro de validação.
    const index = steps.findIndex(step => step.contains(event.target));
    if (index >= 0 && index !== current) { current = index; render(); }
  }, true);
  render();
}
