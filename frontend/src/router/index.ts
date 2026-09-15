import { createRouter, createWebHashHistory } from 'vue-router';
import { useAuth } from '../stores/auth';

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
    {
      path: '/',
      component: () => import('../views/AppLayout.vue'),
      children: [
        { path: '', redirect: '/workbench' },
        { path: 'workbench', name: 'workbench', component: () => import('../views/WorkbenchView.vue') },
        { path: 'tasks', name: 'tasks', component: () => import('../views/InspectorTasksView.vue') },
        { path: 'orders', name: 'orders', component: () => import('../views/RectifierOrdersView.vue') },
        { path: 'people', name: 'people', component: () => import('../views/PeopleView.vue') },
        { path: 'escalations', name: 'escalations', component: () => import('../views/SupervisorView.vue') },
        { path: 'tasks/:id', name: 'task-detail', component: () => import('../views/TaskDetailView.vue'), props: true },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuth();
  await auth.restore();
  if (!to.meta.public && !auth.state.user) {
    return { name: 'login', query: { redirect: to.fullPath } };
  }
  if (to.name === 'login' && auth.state.user) {
    return { name: 'workbench' };
  }
  return true;
});

export default router;
